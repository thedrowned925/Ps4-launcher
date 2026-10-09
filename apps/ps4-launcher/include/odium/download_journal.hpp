#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace odium {

// Portable in-memory ledger for one immutable PKG. The PS4 adapter is
// responsible for data flush, chunk SHA-256, and atomic journal replacement.
class DownloadJournal {
public:
    DownloadJournal(std::string sha256, std::uint64_t file_size,
                    std::uint64_t chunk_size);

    // Only call AFTER the respective byte range has been hash-verified and
    // durably flushed to the file. Never use the journal as proof without
    // rechecking suspect ranges after a crash.
    void MarkVerifiedAfterFlush(std::size_t index);

    bool IsVerified(std::size_t index) const;
    std::size_t ChunkCount() const noexcept;
    std::uint64_t VerifiedBytes() const noexcept;

    // Binary checkpoint. Includes an error-detection CRC32 (not a security MAC).
    std::string Serialize() const;
    static DownloadJournal Deserialize(
        std::string_view contents, std::string_view expected_sha256,
        std::uint64_t expected_size, std::uint64_t expected_chunk_size);

private:
    std::string sha256_;
    std::uint64_t size_;
    std::uint64_t chunk_size_;
    std::vector<std::uint8_t> verified_;
};
}  // namespace odium
