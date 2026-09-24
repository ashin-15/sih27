// Isolated LMDB process-kill, duplicate, and map-limit experiment.
#include <lmdb.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace fs = std::filesystem;

void check(int code, const char* operation) {
  if (code != MDB_SUCCESS) {
    throw std::runtime_error(std::string(operation) + ": " + mdb_strerror(code));
  }
}

std::vector<unsigned char> scan(const fs::path& path) {
  std::ifstream input(path, std::ios::binary | std::ios::ate);
  if (!input || input.tellg() <= 0) {
    throw std::runtime_error("missing source scan");
  }
  std::vector<unsigned char> data(static_cast<std::size_t>(input.tellg()));
  input.seekg(0);
  input.read(reinterpret_cast<char*>(data.data()), static_cast<std::streamsize>(data.size()));
  if (!input) {
    throw std::runtime_error("short source scan");
  }
  return data;
}

MDB_env* environment(const fs::path& path, std::size_t map_bytes) {
  MDB_env* env = nullptr;
  check(mdb_env_create(&env), "create environment");
  check(mdb_env_set_mapsize(env, map_bytes), "set map limit");
  check(mdb_env_open(env, path.c_str(), 0, 0644), "open environment");
  return env;
}

MDB_dbi database(MDB_env* env) {
  MDB_txn* txn = nullptr;
  check(mdb_txn_begin(env, nullptr, 0, &txn), "begin setup");
  MDB_dbi dbi = 0;
  check(mdb_dbi_open(txn, nullptr, MDB_CREATE, &dbi), "open database");
  check(mdb_txn_commit(txn), "commit setup");
  return dbi;
}

int put(MDB_txn* txn, MDB_dbi dbi, std::uint64_t id,
        const std::vector<unsigned char>& payload) {
  MDB_val key{sizeof(id), &id};
  MDB_val value{payload.size(), const_cast<unsigned char*>(payload.data())};
  return mdb_put(txn, dbi, &key, &value, MDB_NOOVERWRITE);
}

void committed(MDB_env* env, MDB_dbi dbi, std::uint64_t id,
               const std::vector<unsigned char>& payload) {
  MDB_txn* txn = nullptr;
  check(mdb_txn_begin(env, nullptr, 0, &txn), "begin write");
  check(put(txn, dbi, id, payload), "put scan");
  check(mdb_txn_commit(txn), "commit scan");
}

std::size_t verify(MDB_env* env, MDB_dbi dbi,
                   const std::vector<unsigned char>& payload) {
  MDB_txn* txn = nullptr;
  check(mdb_txn_begin(env, nullptr, MDB_RDONLY, &txn), "begin verification");
  MDB_stat stats{};
  check(mdb_stat(txn, dbi, &stats), "read count");
  for (std::uint64_t id = 0; id < stats.ms_entries; ++id) {
    MDB_val key{sizeof(id), &id};
    MDB_val value{};
    check(mdb_get(txn, dbi, &key, &value), "read scan");
    if (value.mv_size != payload.size() ||
        std::memcmp(value.mv_data, payload.data(), payload.size()) != 0) {
      throw std::runtime_error("payload mismatch");
    }
  }
  mdb_txn_abort(txn);
  return stats.ms_entries;
}

void signal_parent(int descriptor) {
  const char marker = 'x';
  if (::write(descriptor, &marker, 1) != 1) {
    throw std::runtime_error("pipe write failed");
  }
}

void await_child(int descriptor) {
  char marker = 0;
  if (::read(descriptor, &marker, 1) != 1 || marker != 'x') {
    throw std::runtime_error("child did not reach fault point");
  }
}

int main(int argc, char* argv[]) {
  try {
    if (argc != 3 || fs::exists(argv[2])) {
      throw std::runtime_error("usage: lmdb-faults SOURCE_SCAN NEW_OUTPUT_DIRECTORY");
    }
    const auto payload = scan(argv[1]);
    const fs::path root = argv[2];
    fs::create_directories(root / "killed");
    fs::create_directory(root / "mapfull");
    int pipe_fds[2]{};
    if (::pipe(pipe_fds) != 0) {
      throw std::runtime_error("pipe failed");
    }
    const pid_t child = ::fork();
    if (child < 0) {
      throw std::runtime_error("fork failed");
    }
    if (child == 0) {
      ::close(pipe_fds[0]);
      try {
        MDB_env* env = environment(root / "killed", 64ULL * 1024 * 1024);
        const MDB_dbi dbi = database(env);
        committed(env, dbi, 0, payload);
        signal_parent(pipe_fds[1]);
        MDB_txn* txn = nullptr;
        check(mdb_txn_begin(env, nullptr, 0, &txn), "begin uncommitted scan");
        check(put(txn, dbi, 1, payload), "put uncommitted scan");
        signal_parent(pipe_fds[1]);
        for (;;) {
          ::pause();
        }
      } catch (const std::exception& error) {
        std::cerr << "child: " << error.what() << '\n';
        _exit(1);
      }
    }
    ::close(pipe_fds[1]);
    await_child(pipe_fds[0]);
    await_child(pipe_fds[0]);
    ::close(pipe_fds[0]);
    if (::kill(child, SIGKILL) != 0) {
      throw std::runtime_error("kill failed");
    }
    int status = 0;
    if (::waitpid(child, &status, 0) != child || !WIFSIGNALED(status) ||
        WTERMSIG(status) != SIGKILL) {
      throw std::runtime_error("unexpected child status");
    }
    MDB_env* recovered = environment(root / "killed", 64ULL * 1024 * 1024);
    const MDB_dbi recovered_db = database(recovered);
    if (verify(recovered, recovered_db, payload) != 1) {
      throw std::runtime_error("uncommitted scan survived kill");
    }
    MDB_txn* duplicate = nullptr;
    check(mdb_txn_begin(recovered, nullptr, 0, &duplicate), "begin duplicate");
    const int duplicate_result = put(duplicate, recovered_db, 0, payload);
    mdb_txn_abort(duplicate);
    if (duplicate_result != MDB_KEYEXIST) {
      throw std::runtime_error("duplicate was not rejected");
    }
    committed(recovered, recovered_db, 1, payload);
    if (verify(recovered, recovered_db, payload) != 2) {
      throw std::runtime_error("restart did not resume contiguously");
    }
    mdb_dbi_close(recovered, recovered_db);
    mdb_env_close(recovered);

    MDB_env* bounded = environment(root / "mapfull", 8ULL * 1024 * 1024);
    const MDB_dbi bounded_db = database(bounded);
    std::size_t successful = 0;
    int failure = MDB_SUCCESS;
    for (std::uint64_t id = 0; id < 100; ++id) {
      MDB_txn* txn = nullptr;
      check(mdb_txn_begin(bounded, nullptr, 0, &txn), "begin bounded write");
      failure = put(txn, bounded_db, id, payload);
      if (failure != MDB_SUCCESS) {
        mdb_txn_abort(txn);
        break;
      }
      failure = mdb_txn_commit(txn);
      if (failure != MDB_SUCCESS) {
        break;
      }
      ++successful;
    }
    if (failure != MDB_MAP_FULL || successful == 0 ||
        verify(bounded, bounded_db, payload) != successful) {
      throw std::runtime_error("map limit did not preserve committed prefix");
    }
    mdb_dbi_close(bounded, bounded_db);
    mdb_env_close(bounded);
    std::cout << "kill: committed 1, uncommitted 1 rolled back, duplicate rejected, "
              << "resumed to 2; artificial map limit: " << successful
              << " committed before MDB_MAP_FULL; all reverified\n";
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
  return 0;
}
