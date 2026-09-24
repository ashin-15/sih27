// Isolated paced recorder comparison. No Drishti runtime path uses this code.
#include <fcntl.h>
#include <lmdb.h>
#include <openssl/evp.h>
#include <sqlite3.h>
#include <sys/stat.h>
#include <unistd.h>

#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;
using Digest = std::array<unsigned char, 32>;

#pragma pack(push, 1)
struct RecordHeader {
  std::uint64_t magic;
  std::uint32_t version;
  std::uint64_t frame_id;
  std::int64_t capture_ns;
  std::uint64_t payload_bytes;
  std::uint32_t point_count;
  Digest sha256;
};
#pragma pack(pop)
static_assert(sizeof(RecordHeader) == 72);
constexpr std::uint64_t kMagic = 0x4452495348544932ULL;

struct Timing {
  int id;
  std::size_t bytes;
  double schedule_lag_ms;
  double read_ms;
  double hash_ms;
  double commit_ms;
  double acquisition_ms;
};

double milliseconds(Clock::time_point first, Clock::time_point last) {
  return std::chrono::duration<double, std::milli>(last - first).count();
}

void check_system(int result, const std::string& what) {
  if (result == -1) {
    throw std::runtime_error(what + ": " + std::strerror(errno));
  }
}

void check_lmdb(int result, const std::string& what) {
  if (result != MDB_SUCCESS) {
    throw std::runtime_error(what + ": " + mdb_strerror(result));
  }
}

void check_sqlite(int result, sqlite3* db, const std::string& what) {
  if (result != SQLITE_OK && result != SQLITE_DONE && result != SQLITE_ROW) {
    throw std::runtime_error(what + ": " + sqlite3_errmsg(db));
  }
}

void sql(sqlite3* db, const char* statement) {
  char* error = nullptr;
  const int result = sqlite3_exec(db, statement, nullptr, nullptr, &error);
  if (result != SQLITE_OK) {
    const std::string message = error == nullptr ? sqlite3_errmsg(db) : error;
    sqlite3_free(error);
    throw std::runtime_error(message);
  }
}

void require_pragma(sqlite3* db, const char* statement, const char* expected) {
  sqlite3_stmt* query = nullptr;
  check_sqlite(sqlite3_prepare_v2(db, statement, -1, &query, nullptr), db,
               "prepare SQLite pragma check");
  const int result = sqlite3_step(query);
  const auto* actual = result == SQLITE_ROW ? sqlite3_column_text(query, 0) : nullptr;
  const bool matches = actual != nullptr && std::strcmp(
      reinterpret_cast<const char*>(actual), expected) == 0;
  check_sqlite(sqlite3_finalize(query), db, "finalize SQLite pragma check");
  if (!matches) {
    throw std::runtime_error(std::string("SQLite pragma mismatch: ") + statement);
  }
}

void write_all(int fd, const void* data, std::size_t bytes) {
  const auto* current = static_cast<const unsigned char*>(data);
  while (bytes > 0) {
    const auto result = ::write(fd, current, bytes);
    check_system(static_cast<int>(result), "write");
    if (result == 0) {
      throw std::runtime_error("write returned zero");
    }
    bytes -= static_cast<std::size_t>(result);
    current += result;
  }
}

void read_all(int fd, void* data, std::size_t bytes) {
  auto* current = static_cast<unsigned char*>(data);
  while (bytes > 0) {
    const auto result = ::read(fd, current, bytes);
    check_system(static_cast<int>(result), "read");
    if (result == 0) {
      throw std::runtime_error("unexpected end of record");
    }
    bytes -= static_cast<std::size_t>(result);
    current += result;
  }
}

void sync_directory(const fs::path& directory) {
  const int fd = ::open(directory.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
  check_system(fd, "open directory");
  const int result = ::fsync(fd);
  const int saved_errno = errno;
  ::close(fd);
  errno = saved_errno;
  check_system(result, "sync directory");
}

fs::path scan_path(const fs::path& dataset, const std::string& sequence, int id) {
  std::ostringstream filename;
  filename << std::setw(6) << std::setfill('0') << id << ".bin";
  return dataset / "sequences" / sequence / "velodyne" / filename.str();
}

std::vector<unsigned char> scan_bytes(const fs::path& path) {
  std::ifstream stream(path, std::ios::binary | std::ios::ate);
  if (!stream) {
    throw std::runtime_error("missing scan: " + path.string());
  }
  const auto size = stream.tellg();
  if (size <= 0 || size % 16 != 0) {
    throw std::runtime_error("invalid scan size: " + path.string());
  }
  std::vector<unsigned char> data(static_cast<std::size_t>(size));
  stream.seekg(0);
  stream.read(reinterpret_cast<char*>(data.data()), size);
  if (!stream) {
    throw std::runtime_error("incomplete scan read: " + path.string());
  }
  return data;
}

Digest sha256(const unsigned char* data, std::size_t bytes) {
  Digest digest{};
  unsigned int size = 0;
  if (EVP_Digest(data, bytes, digest.data(), &size, EVP_sha256(), nullptr) != 1 ||
      size != digest.size()) {
    throw std::runtime_error("SHA-256 failed");
  }
  return digest;
}

RecordHeader header_for(int id, std::int64_t capture_ns,
                        const std::vector<unsigned char>& payload, const Digest& digest) {
  return {kMagic, 1U, static_cast<std::uint64_t>(id), capture_ns,
          static_cast<std::uint64_t>(payload.size()),
          static_cast<std::uint32_t>(payload.size() / 16), digest};
}

void verify_record(const RecordHeader& header, const unsigned char* payload,
                   std::size_t payload_bytes, int expected_id, const fs::path& source) {
  const auto original = scan_bytes(source);
  if (header.magic != kMagic || header.version != 1 ||
      header.frame_id != static_cast<std::uint64_t>(expected_id) ||
      header.payload_bytes != payload_bytes || header.point_count * 16 != payload_bytes ||
      original.size() != payload_bytes ||
      sha256(payload, payload_bytes) != header.sha256 ||
      sha256(original.data(), original.size()) != header.sha256) {
    throw std::runtime_error("reopened payload does not match source");
  }
}

class Store {
 public:
  virtual ~Store() = default;
  virtual void append(const RecordHeader& header,
                      const std::vector<unsigned char>& payload) = 0;
  virtual void verify(const fs::path& dataset, const std::string& sequence, int frames) = 0;
  virtual std::uint64_t logical_bytes() const = 0;
  virtual std::uint64_t allocated_bytes() const = 0;
};

std::uint64_t allocated_file_bytes(const fs::path& path) {
  struct stat info {};
  check_system(::stat(path.c_str(), &info), "stat store");
  return static_cast<std::uint64_t>(info.st_blocks) * 512;
}

class LogStore final : public Store {
 public:
  explicit LogStore(const fs::path& directory) : path_(directory / "scans.log") {
    fd_ = ::open(path_.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0644);
    check_system(fd_, "create log");
    sync_directory(directory);
  }

  ~LogStore() override {
    if (fd_ >= 0) {
      ::close(fd_);
    }
  }

  void append(const RecordHeader& header,
              const std::vector<unsigned char>& payload) override {
    write_all(fd_, &header, sizeof(header));
    write_all(fd_, payload.data(), payload.size());
    check_system(::fdatasync(fd_), "sync log record");
  }

  void verify(const fs::path& dataset, const std::string& sequence, int frames) override {
    check_system(::close(fd_), "close log writer");
    fd_ = -1;
    const int reader = ::open(path_.c_str(), O_RDONLY | O_CLOEXEC);
    check_system(reader, "open log reader");
    try {
      for (int id = 0; id < frames; ++id) {
        RecordHeader header{};
        read_all(reader, &header, sizeof(header));
        if (header.payload_bytes > 16ULL * 150000ULL || header.payload_bytes % 16 != 0) {
          throw std::runtime_error("invalid log record length");
        }
        std::vector<unsigned char> payload(header.payload_bytes);
        read_all(reader, payload.data(), payload.size());
        verify_record(header, payload.data(), payload.size(), id,
                      scan_path(dataset, sequence, id));
      }
      unsigned char extra = 0;
      if (::read(reader, &extra, 1) != 0) {
        throw std::runtime_error("unexpected extra log record");
      }
      ::close(reader);
    } catch (...) {
      ::close(reader);
      throw;
    }
  }

  std::uint64_t logical_bytes() const override { return fs::file_size(path_); }
  std::uint64_t allocated_bytes() const override { return allocated_file_bytes(path_); }

 private:
  fs::path path_;
  int fd_ = -1;
};

class LmdbStore final : public Store {
 public:
  explicit LmdbStore(const fs::path& directory) : data_path_(directory / "data.mdb") {
    check_lmdb(mdb_env_create(&environment_), "create LMDB environment");
    check_lmdb(mdb_env_set_mapsize(environment_, 8ULL * 1024 * 1024 * 1024),
               "set LMDB map limit");
    check_lmdb(mdb_env_open(environment_, directory.c_str(), 0, 0644),
               "open LMDB environment");
    sync_directory(directory);
    MDB_txn* transaction = nullptr;
    check_lmdb(mdb_txn_begin(environment_, nullptr, 0, &transaction), "begin LMDB setup");
    check_lmdb(mdb_dbi_open(transaction, nullptr, MDB_CREATE, &dbi_), "open LMDB table");
    check_lmdb(mdb_txn_commit(transaction), "commit LMDB setup");
  }

  ~LmdbStore() override {
    if (environment_ != nullptr) {
      mdb_dbi_close(environment_, dbi_);
      mdb_env_close(environment_);
    }
  }

  void append(const RecordHeader& header,
              const std::vector<unsigned char>& payload) override {
    MDB_txn* transaction = nullptr;
    check_lmdb(mdb_txn_begin(environment_, nullptr, 0, &transaction), "begin LMDB write");
    const auto key_bytes = big_endian(header.frame_id);
    MDB_val key{key_bytes.size(), const_cast<unsigned char*>(key_bytes.data())};
    MDB_val value{sizeof(header) + payload.size(), nullptr};
    const int result = mdb_put(transaction, dbi_, &key, &value, MDB_NOOVERWRITE | MDB_RESERVE);
    if (result != MDB_SUCCESS) {
      mdb_txn_abort(transaction);
      check_lmdb(result, "reserve LMDB payload");
    }
    std::memcpy(value.mv_data, &header, sizeof(header));
    std::memcpy(static_cast<unsigned char*>(value.mv_data) + sizeof(header),
                payload.data(), payload.size());
    check_lmdb(mdb_txn_commit(transaction), "commit LMDB scan");
  }

  void verify(const fs::path& dataset, const std::string& sequence, int frames) override {
    mdb_dbi_close(environment_, dbi_);
    mdb_env_close(environment_);
    environment_ = nullptr;
    check_lmdb(mdb_env_create(&environment_), "recreate LMDB environment");
    check_lmdb(mdb_env_set_mapsize(environment_, 8ULL * 1024 * 1024 * 1024),
               "set reopened LMDB map limit");
    check_lmdb(mdb_env_open(environment_, data_path_.parent_path().c_str(), MDB_RDONLY, 0644),
               "reopen LMDB environment");
    MDB_txn* transaction = nullptr;
    check_lmdb(mdb_txn_begin(environment_, nullptr, MDB_RDONLY, &transaction),
               "begin LMDB verification");
    check_lmdb(mdb_dbi_open(transaction, nullptr, 0, &dbi_), "open LMDB verification table");
    MDB_stat stats{};
    check_lmdb(mdb_stat(transaction, dbi_, &stats), "read LMDB row count");
    if (stats.ms_entries != static_cast<std::size_t>(frames)) {
      throw std::runtime_error("LMDB row count mismatch");
    }
    for (int id = 0; id < frames; ++id) {
      const auto key_bytes = big_endian(static_cast<std::uint64_t>(id));
      MDB_val key{key_bytes.size(), const_cast<unsigned char*>(key_bytes.data())};
      MDB_val value{};
      check_lmdb(mdb_get(transaction, dbi_, &key, &value), "read LMDB scan");
      if (value.mv_size < sizeof(RecordHeader)) {
        throw std::runtime_error("short LMDB value");
      }
      RecordHeader header{};
      std::memcpy(&header, value.mv_data, sizeof(header));
      verify_record(header, static_cast<const unsigned char*>(value.mv_data) + sizeof(header),
                    value.mv_size - sizeof(header), id, scan_path(dataset, sequence, id));
    }
    mdb_txn_abort(transaction);
  }

  std::uint64_t logical_bytes() const override { return fs::file_size(data_path_); }
  std::uint64_t allocated_bytes() const override { return allocated_file_bytes(data_path_); }

 private:
  static std::array<unsigned char, 8> big_endian(std::uint64_t value) {
    std::array<unsigned char, 8> result{};
    for (int i = 7; i >= 0; --i) {
      result[i] = static_cast<unsigned char>(value & 0xff);
      value >>= 8;
    }
    return result;
  }

  fs::path data_path_;
  MDB_env* environment_ = nullptr;
  MDB_dbi dbi_ = 0;
};

class SqliteStore final : public Store {
 public:
  explicit SqliteStore(const fs::path& directory) : path_(directory / "scans.sqlite") {
    check_sqlite(sqlite3_open_v2(path_.c_str(), &db_,
                     SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE, nullptr), db_, "open SQLite");
    sql(db_, "PRAGMA journal_mode=WAL");
    sql(db_, "PRAGMA synchronous=FULL");
    require_pragma(db_, "PRAGMA journal_mode", "wal");
    require_pragma(db_, "PRAGMA synchronous", "2");
    sql(db_, "CREATE TABLE scans(id INTEGER PRIMARY KEY, capture_ns INTEGER NOT NULL, "
             "points INTEGER NOT NULL, sha BLOB NOT NULL, payload BLOB NOT NULL)");
    sync_directory(directory);
    check_sqlite(sqlite3_prepare_v2(db_, "INSERT INTO scans VALUES(?,?,?,?,?)", -1,
                     &insert_, nullptr), db_, "prepare SQLite insert");
  }

  ~SqliteStore() override {
    if (insert_ != nullptr) {
      sqlite3_finalize(insert_);
    }
    if (db_ != nullptr) {
      sqlite3_close(db_);
    }
  }

  void append(const RecordHeader& header,
              const std::vector<unsigned char>& payload) override {
    sql(db_, "BEGIN IMMEDIATE");
    check_sqlite(sqlite3_bind_int64(insert_, 1, static_cast<sqlite3_int64>(header.frame_id)),
                 db_, "bind SQLite ID");
    check_sqlite(sqlite3_bind_int64(insert_, 2, header.capture_ns), db_, "bind SQLite time");
    check_sqlite(sqlite3_bind_int(insert_, 3, static_cast<int>(header.point_count)),
                 db_, "bind SQLite point count");
    check_sqlite(sqlite3_bind_blob(insert_, 4, header.sha256.data(), header.sha256.size(),
                                  SQLITE_STATIC), db_, "bind SQLite digest");
    check_sqlite(sqlite3_bind_blob64(insert_, 5, payload.data(), payload.size(),
                                    SQLITE_STATIC), db_, "bind SQLite payload");
    check_sqlite(sqlite3_step(insert_), db_, "insert SQLite scan");
    check_sqlite(sqlite3_reset(insert_), db_, "reset SQLite insert");
    check_sqlite(sqlite3_clear_bindings(insert_), db_, "clear SQLite bindings");
    sql(db_, "COMMIT");
  }

  void verify(const fs::path& dataset, const std::string& sequence, int frames) override {
    check_sqlite(sqlite3_finalize(insert_), db_, "finalize SQLite insert");
    insert_ = nullptr;
    check_sqlite(sqlite3_close(db_), db_, "close SQLite writer");
    db_ = nullptr;
    check_sqlite(sqlite3_open_v2(path_.c_str(), &db_, SQLITE_OPEN_READONLY, nullptr), db_,
                 "reopen SQLite");
    sqlite3_stmt* reader = nullptr;
    check_sqlite(sqlite3_prepare_v2(db_,
        "SELECT id,capture_ns,points,sha,payload FROM scans ORDER BY id", -1,
        &reader, nullptr), db_, "prepare SQLite verification");
    for (int id = 0; id < frames; ++id) {
      if (sqlite3_step(reader) != SQLITE_ROW) {
        throw std::runtime_error("missing SQLite scan");
      }
      RecordHeader header{};
      header.magic = kMagic;
      header.version = 1;
      header.frame_id = static_cast<std::uint64_t>(sqlite3_column_int64(reader, 0));
      header.capture_ns = sqlite3_column_int64(reader, 1);
      header.point_count = static_cast<std::uint32_t>(sqlite3_column_int(reader, 2));
      const auto* hash = sqlite3_column_blob(reader, 3);
      const auto* payload = static_cast<const unsigned char*>(sqlite3_column_blob(reader, 4));
      const auto size = static_cast<std::size_t>(sqlite3_column_bytes(reader, 4));
      if (hash == nullptr || sqlite3_column_bytes(reader, 3) != 32 || payload == nullptr) {
        throw std::runtime_error("invalid SQLite BLOB");
      }
      std::memcpy(header.sha256.data(), hash, 32);
      header.payload_bytes = size;
      verify_record(header, payload, size, id, scan_path(dataset, sequence, id));
    }
    if (sqlite3_step(reader) != SQLITE_DONE) {
      throw std::runtime_error("unexpected SQLite scan");
    }
    check_sqlite(sqlite3_finalize(reader), db_, "finalize SQLite reader");
    check_sqlite(sqlite3_close(db_), db_, "close SQLite verifier");
    db_ = nullptr;
  }

  std::uint64_t logical_bytes() const override { return fs::file_size(path_); }
  std::uint64_t allocated_bytes() const override { return allocated_file_bytes(path_); }

 private:
  fs::path path_;
  sqlite3* db_ = nullptr;
  sqlite3_stmt* insert_ = nullptr;
};

int main(int argc, char* argv[]) {
  try {
    if (argc != 8) {
      throw std::runtime_error(
          "usage: storage-backends BACKEND DATASET SEQUENCE FRAMES INTERVAL_MS NEW_DIR NEW_CSV");
    }
    const std::string backend = argv[1];
    const fs::path dataset = fs::canonical(argv[2]);
    const std::string sequence = argv[3];
    const int frames = std::stoi(argv[4]);
    const double interval_ms = std::stod(argv[5]);
    const fs::path directory = fs::absolute(argv[6]);
    const fs::path csv_path = fs::absolute(argv[7]);
    if (frames < 2 || interval_ms <= 0 || fs::exists(directory) || fs::exists(csv_path) ||
        directory.string().starts_with(dataset.string()) ||
        csv_path.string().starts_with(dataset.string())) {
      throw std::runtime_error("invalid arguments or output already exists");
    }
    fs::create_directory(directory);
    sync_directory(directory.parent_path());
    std::unique_ptr<Store> store;
    if (backend == "log") {
      store = std::make_unique<LogStore>(directory);
    } else if (backend == "lmdb") {
      store = std::make_unique<LmdbStore>(directory);
    } else if (backend == "sqlite") {
      store = std::make_unique<SqliteStore>(directory);
    } else {
      throw std::runtime_error("backend must be log, lmdb or sqlite");
    }
    std::vector<Timing> measurements;
    measurements.reserve(static_cast<std::size_t>(frames));
    const auto start = Clock::now();
    for (int id = 0; id < frames; ++id) {
      const auto due = start + std::chrono::duration_cast<Clock::duration>(
          std::chrono::duration<double, std::milli>(id * interval_ms));
      std::this_thread::sleep_until(due);
      const auto began = Clock::now();
      const auto payload = scan_bytes(scan_path(dataset, sequence, id));
      const auto read_done = Clock::now();
      const auto digest = sha256(payload.data(), payload.size());
      const auto hash_done = Clock::now();
      const auto capture_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::system_clock::now().time_since_epoch()).count();
      store->append(header_for(id, capture_ns, payload, digest), payload);
      const auto committed = Clock::now();
      measurements.push_back({id, payload.size(), milliseconds(due, began),
                              milliseconds(began, read_done),
                              milliseconds(read_done, hash_done),
                              milliseconds(hash_done, committed),
                              milliseconds(began, committed)});
    }
    std::ofstream csv(csv_path, std::ios::out | std::ios::trunc);
    if (!csv) {
      throw std::runtime_error("cannot create timing CSV");
    }
    csv << "frame_id,bytes,schedule_lag_ms,read_ms,hash_ms,commit_ms,acquisition_ms\n";
    csv << std::fixed << std::setprecision(6);
    for (const auto& row : measurements) {
      csv << row.id << ',' << row.bytes << ',' << row.schedule_lag_ms << ',' << row.read_ms
          << ',' << row.hash_ms << ',' << row.commit_ms << ',' << row.acquisition_ms << '\n';
    }
    if (!csv) {
      throw std::runtime_error("timing CSV write failed");
    }
    csv.close();
    store->verify(dataset, sequence, frames);
    std::cout << backend << " verified " << frames << " scans; logical bytes "
              << store->logical_bytes() << "; allocated bytes " << store->allocated_bytes()
              << '\n';
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
  return 0;
}
