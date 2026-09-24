// Isolated C++ SQLite WAL recorder benchmark. This is not production Drishti code.
#include <openssl/evp.h>
#include <sqlite3.h>

#include <array>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

struct Timing {
  int frame_id;
  std::size_t bytes;
  double schedule_lag_ms;
  double read_ms;
  double hash_ms;
  double commit_ms;
  double acquisition_ms;
};

double elapsed_ms(Clock::time_point start, Clock::time_point end) {
  return std::chrono::duration<double, std::milli>(end - start).count();
}

void check_sqlite(int code, sqlite3* db, const std::string& action) {
  if (code != SQLITE_OK && code != SQLITE_DONE && code != SQLITE_ROW) {
    throw std::runtime_error(action + ": " + sqlite3_errmsg(db));
  }
}

void exec_sql(sqlite3* db, const char* sql) {
  char* error = nullptr;
  const int code = sqlite3_exec(db, sql, nullptr, nullptr, &error);
  if (code != SQLITE_OK) {
    const std::string message = error == nullptr ? sqlite3_errmsg(db) : error;
    sqlite3_free(error);
    throw std::runtime_error(message);
  }
}

std::string scalar_text(sqlite3* db, const char* sql) {
  sqlite3_stmt* statement = nullptr;
  check_sqlite(sqlite3_prepare_v2(db, sql, -1, &statement, nullptr), db, "prepare pragma");
  try {
    check_sqlite(sqlite3_step(statement), db, "read pragma");
    const auto* value = sqlite3_column_text(statement, 0);
    const std::string result = value == nullptr ? "" : reinterpret_cast<const char*>(value);
    sqlite3_finalize(statement);
    return result;
  } catch (...) {
    sqlite3_finalize(statement);
    throw;
  }
}

std::vector<unsigned char> read_bytes(const fs::path& path) {
  std::ifstream input(path, std::ios::binary | std::ios::ate);
  if (!input) {
    throw std::runtime_error("cannot open scan: " + path.string());
  }
  const auto end = input.tellg();
  if (end <= 0 || end % 16 != 0) {
    throw std::runtime_error("invalid scan length: " + path.string());
  }
  std::vector<unsigned char> bytes(static_cast<std::size_t>(end));
  input.seekg(0);
  input.read(reinterpret_cast<char*>(bytes.data()), end);
  if (!input) {
    throw std::runtime_error("cannot read complete scan: " + path.string());
  }
  return bytes;
}

std::string sha256_hex(const unsigned char* bytes, std::size_t count) {
  std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
  unsigned int digest_size = 0;
  if (EVP_Digest(bytes, count, digest.data(), &digest_size, EVP_sha256(), nullptr) != 1 ||
      digest_size != 32) {
    throw std::runtime_error("SHA-256 failed");
  }
  constexpr char hex[] = "0123456789abcdef";
  std::string result(64, '0');
  for (unsigned int i = 0; i < digest_size; ++i) {
    result[2 * i] = hex[digest[i] >> 4];
    result[2 * i + 1] = hex[digest[i] & 15];
  }
  return result;
}

fs::path scan_path(const fs::path& dataset, const std::string& sequence, int frame_id) {
  std::ostringstream name;
  name << std::setw(6) << std::setfill('0') << frame_id << ".bin";
  return dataset / "sequences" / sequence / "velodyne" / name.str();
}

void verify(sqlite3* db, const fs::path& dataset, const std::string& sequence, int frames) {
  sqlite3_stmt* statement = nullptr;
  check_sqlite(sqlite3_prepare_v2(db,
      "SELECT frame_id,points,sha256,payload FROM scans WHERE sequence=? ORDER BY frame_id",
      -1, &statement, nullptr), db, "prepare verification");
  check_sqlite(sqlite3_bind_text(statement, 1, sequence.c_str(), -1, SQLITE_TRANSIENT), db,
               "bind verification sequence");
  try {
    for (int expected = 0; expected < frames; ++expected) {
      if (sqlite3_step(statement) != SQLITE_ROW) {
        throw std::runtime_error("missing committed scan");
      }
      const int id = sqlite3_column_int(statement, 0);
      const int points = sqlite3_column_int(statement, 1);
      const auto* stored_hash = reinterpret_cast<const char*>(sqlite3_column_text(statement, 2));
      const auto* payload = static_cast<const unsigned char*>(sqlite3_column_blob(statement, 3));
      const int size = sqlite3_column_bytes(statement, 3);
      const auto source = read_bytes(scan_path(dataset, sequence, expected));
      if (id != expected || points * 16 != size || source.size() != static_cast<std::size_t>(size) ||
          stored_hash == nullptr || payload == nullptr ||
          sha256_hex(payload, source.size()) != stored_hash ||
          sha256_hex(source.data(), source.size()) != stored_hash) {
        throw std::runtime_error("committed scan verification failed");
      }
    }
    if (sqlite3_step(statement) != SQLITE_DONE) {
      throw std::runtime_error("unexpected extra committed scan");
    }
    sqlite3_finalize(statement);
  } catch (...) {
    sqlite3_finalize(statement);
    throw;
  }
}

int main(int argc, char* argv[]) {
  try {
    if (argc != 7) {
      throw std::runtime_error(
          "usage: recorder DATASET SEQUENCE FRAMES INTERVAL_MS NEW_DB NEW_CSV");
    }
    const fs::path dataset = fs::canonical(argv[1]);
    const std::string sequence = argv[2];
    const int frames = std::stoi(argv[3]);
    const double interval_ms = std::stod(argv[4]);
    const fs::path db_path = fs::absolute(argv[5]);
    const fs::path csv_path = fs::absolute(argv[6]);
    if (frames < 2 || interval_ms <= 0 || fs::exists(db_path) || fs::exists(csv_path)) {
      throw std::runtime_error("invalid frame/interval count or output already exists");
    }
    if (db_path.string().starts_with(dataset.string()) ||
        csv_path.string().starts_with(dataset.string())) {
      throw std::runtime_error("output must be outside the source dataset");
    }
    sqlite3* db = nullptr;
    check_sqlite(sqlite3_open_v2(db_path.c_str(), &db,
        SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX, nullptr), db,
        "open database");
    try {
      if (scalar_text(db, "PRAGMA journal_mode=WAL") != "wal") {
        throw std::runtime_error("WAL mode unavailable");
      }
      exec_sql(db, "PRAGMA synchronous=FULL");
      if (scalar_text(db, "PRAGMA synchronous") != "2") {
        throw std::runtime_error("FULL synchronization unavailable");
      }
      exec_sql(db,
          "CREATE TABLE scans (sequence TEXT NOT NULL, frame_id INTEGER NOT NULL, "
          "capture_ns INTEGER NOT NULL, points INTEGER NOT NULL, sha256 TEXT NOT NULL, "
          "payload BLOB NOT NULL, PRIMARY KEY(sequence,frame_id))");
      sqlite3_stmt* insert = nullptr;
      check_sqlite(sqlite3_prepare_v2(db, "INSERT INTO scans VALUES(?,?,?,?,?,?)", -1,
          &insert, nullptr), db, "prepare insert");
      std::vector<Timing> rows;
      rows.reserve(static_cast<std::size_t>(frames));
      const auto start = Clock::now();
      for (int id = 0; id < frames; ++id) {
        const auto due = start + std::chrono::duration_cast<Clock::duration>(
            std::chrono::duration<double, std::milli>(id * interval_ms));
        std::this_thread::sleep_until(due);
        const auto began = Clock::now();
        const auto bytes = read_bytes(scan_path(dataset, sequence, id));
        const auto loaded = Clock::now();
        const auto digest = sha256_hex(bytes.data(), bytes.size());
        const auto hashed = Clock::now();
        const auto captured_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        exec_sql(db, "BEGIN IMMEDIATE");
        check_sqlite(sqlite3_bind_text(insert, 1, sequence.c_str(), -1, SQLITE_STATIC), db,
                     "bind sequence");
        check_sqlite(sqlite3_bind_int(insert, 2, id), db, "bind frame ID");
        check_sqlite(sqlite3_bind_int64(insert, 3, captured_ns), db, "bind capture time");
        check_sqlite(sqlite3_bind_int(insert, 4, static_cast<int>(bytes.size() / 16)), db,
                     "bind point count");
        check_sqlite(sqlite3_bind_text(insert, 5, digest.c_str(), -1, SQLITE_STATIC), db,
                     "bind SHA-256");
        check_sqlite(sqlite3_bind_blob64(insert, 6, bytes.data(), bytes.size(), SQLITE_STATIC), db,
                     "bind payload");
        check_sqlite(sqlite3_step(insert), db, "insert scan");
        check_sqlite(sqlite3_reset(insert), db, "reset insert");
        check_sqlite(sqlite3_clear_bindings(insert), db, "clear insert bindings");
        exec_sql(db, "COMMIT");
        const auto committed = Clock::now();
        rows.push_back({id, bytes.size(), elapsed_ms(due, began), elapsed_ms(began, loaded),
                        elapsed_ms(loaded, hashed), elapsed_ms(hashed, committed),
                        elapsed_ms(began, committed)});
      }
      check_sqlite(sqlite3_finalize(insert), db, "finalize insert");
      check_sqlite(sqlite3_close(db), db, "close writer");
      db = nullptr;
      check_sqlite(sqlite3_open_v2(db_path.c_str(), &db, SQLITE_OPEN_READONLY, nullptr), db,
                   "reopen database");
      verify(db, dataset, sequence, frames);
      check_sqlite(sqlite3_close(db), db, "close verifier");
      db = nullptr;
      std::ofstream csv(csv_path, std::ios::out | std::ios::trunc);
      if (!csv) {
        throw std::runtime_error("cannot create timing CSV");
      }
      csv << "frame_id,bytes,schedule_lag_ms,read_ms,hash_ms,commit_ms,acquisition_ms\n";
      csv << std::fixed << std::setprecision(6);
      for (const auto& row : rows) {
        csv << row.frame_id << ',' << row.bytes << ',' << row.schedule_lag_ms << ','
            << row.read_ms << ',' << row.hash_ms << ',' << row.commit_ms << ','
            << row.acquisition_ms << '\n';
      }
      if (!csv) {
        throw std::runtime_error("timing CSV write failed");
      }
      std::cout << "verified " << frames << " committed scans; database bytes "
                << fs::file_size(db_path) << '\n';
    } catch (...) {
      sqlite3_close(db);
      throw;
    }
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
  return 0;
}
