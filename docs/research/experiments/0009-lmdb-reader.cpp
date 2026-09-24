// Short-transaction reader for the isolated LMDB recorder comparison.
#include <lmdb.h>
#include <openssl/evp.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <thread>

using Clock = std::chrono::steady_clock;
using Digest = std::array<unsigned char, 32>;
namespace fs = std::filesystem;

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

void check(int result, const char* operation) {
  if (result != MDB_SUCCESS) {
    throw std::runtime_error(std::string(operation) + ": " + mdb_strerror(result));
  }
}

std::array<unsigned char, 8> key_for(std::uint64_t id) {
  std::array<unsigned char, 8> key{};
  for (int index = 7; index >= 0; --index) {
    key[index] = static_cast<unsigned char>(id & 0xff);
    id >>= 8;
  }
  return key;
}

int main(int argc, char* argv[]) {
  try {
    if (argc < 3 || argc > 5) {
      throw std::runtime_error(
          "usage: lmdb-reader EXISTING_LMDB_DIRECTORY FRAMES [HOLD_OPEN_MS] [rw-env]");
    }
    const fs::path directory = fs::canonical(argv[1]);
    const int frames = std::stoi(argv[2]);
    if (frames < 1) {
      throw std::runtime_error("frames must be positive");
    }
    const int hold_open_ms = argc >= 4 ? std::stoi(argv[3]) : 0;
    if (hold_open_ms < 0) {
      throw std::runtime_error("hold time must be nonnegative");
    }
    MDB_env* env = nullptr;
    check(mdb_env_create(&env), "create reader environment");
    check(mdb_env_set_mapsize(env, 8ULL * 1024 * 1024 * 1024), "set reader map limit");
    const bool rw_environment = argc == 5 && std::strcmp(argv[4], "rw-env") == 0;
    if (argc == 5 && !rw_environment) {
      throw std::runtime_error("unknown environment mode");
    }
    check(mdb_env_open(env, directory.c_str(), rw_environment ? 0 : MDB_RDONLY, 0644),
          "open reader environment");
    std::uint64_t retries = 0;
    double max_lookup_ms = 0;
    double max_age_ms = 0;
    for (int id = 0; id < frames; ++id) {
      for (;;) {
        const auto began = Clock::now();
        MDB_txn* txn = nullptr;
        check(mdb_txn_begin(env, nullptr, MDB_RDONLY, &txn), "begin reader transaction");
        MDB_dbi dbi = 0;
        check(mdb_dbi_open(txn, nullptr, 0, &dbi), "open reader database");
        const auto key_bytes = key_for(static_cast<std::uint64_t>(id));
        MDB_val key{key_bytes.size(), const_cast<unsigned char*>(key_bytes.data())};
        MDB_val value{};
        const int result = mdb_get(txn, dbi, &key, &value);
        if (result == MDB_NOTFOUND) {
          mdb_txn_abort(txn);
          ++retries;
          std::this_thread::sleep_for(std::chrono::milliseconds(2));
          continue;
        }
        check(result, "read frame");
        if (value.mv_size < sizeof(RecordHeader)) {
          throw std::runtime_error("short frame record");
        }
        RecordHeader header{};
        std::memcpy(&header, value.mv_data, sizeof(header));
        const auto* payload = static_cast<const unsigned char*>(value.mv_data) + sizeof(header);
        const auto payload_size = value.mv_size - sizeof(header);
        Digest digest{};
        unsigned int digest_size = 0;
        if (EVP_Digest(payload, payload_size, digest.data(), &digest_size,
                       EVP_sha256(), nullptr) != 1 || digest_size != digest.size() ||
            digest != header.sha256 || header.magic != 0x4452495348544932ULL ||
            header.version != 1 || header.frame_id != static_cast<std::uint64_t>(id) ||
            header.payload_bytes != payload_size || header.point_count * 16 != payload_size) {
          throw std::runtime_error("reader record mismatch");
        }
        const auto age_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count() - header.capture_ns;
        const auto completed = Clock::now();
        const double lookup_ms =
            std::chrono::duration<double, std::milli>(completed - began).count();
        max_lookup_ms = std::max(max_lookup_ms, lookup_ms);
        max_age_ms = std::max(max_age_ms, static_cast<double>(age_ns) / 1e6);
        mdb_txn_abort(txn);
        break;
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(hold_open_ms));
    mdb_env_close(env);
    std::cout << "reader verified " << frames << " frames; retries " << retries
              << "; max lookup+hash ms " << std::fixed << std::setprecision(3)
              << max_lookup_ms << "; max recorded-capture-to-read ms " << max_age_ms << '\n';
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
  return 0;
}
