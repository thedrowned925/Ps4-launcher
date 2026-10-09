#include "odium/download_journal.hpp"

#include <algorithm>
#include <limits>
#include <stdexcept>
#include <utility>

namespace odium {
namespace {
constexpr char kMagic[] = "ODIUMDL1";
constexpr std::size_t kMagicLen = 8;
constexpr std::uint64_t kMaxChunks = 1000000;

bool IsDigest(std::string_view str) {
    if (str.size() != 64) return false;
    for (char c : str) {
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')))
            return false;
    }
    return true;
}

void AppendU64(std::string& out, std::uint64_t v) {
    for (int i = 0; i < 8; ++i) {
        out.push_back(static_cast<char>((v >> (i * 8)) & 0xffU));
    }
}
void AppendU32(std::string& out, std::uint32_t v) {
    for (int i = 0; i < 4; ++i) {
        out.push_back(static_cast<char>((v >> (i * 8)) & 0xffU));
    }
}
std::uint64_t ReadU64(std::string_view bytes, std::size_t offset) {
    if (offset > bytes.size() || bytes.size() - offset < 8)
        throw std::invalid_argument("Truncated journal");
    std::uint64_t value = 0;
    for (int i = 0; i < 8; ++i) {
        value |= static_cast<std::uint64_t>(
            static_cast<unsigned char>(bytes[offset + i])) << (8 * i);
    }
    return value;
}
std::uint32_t ReadU32(std::string_view bytes, std::size_t offset) {
    if (offset > bytes.size() || bytes.size() - offset < 4)
        throw std::invalid_argument("Truncated journal");
    std::uint32_t value = 0;
    for (int i = 0; i < 4; ++i) {
        value |= static_cast<std::uint32_t>(
            static_cast<unsigned char>(bytes[offset + i])) << (8 * i);
    }
    return value;
}
std::uint32_t Checksum(std::string_view payload) noexcept {
    std::uint32_t crc = 0xffffffffU;
    for (char byte : payload) {
        crc ^= static_cast<std::uint8_t>(byte);
        for (int bit = 0; bit < 8; ++bit) {
            crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320U : 0U);
        }
    }
    return ~crc;
}
}  // namespace

DownloadJournal::DownloadJournal(std::string sha256, std::uint64_t file_size,
                                 std::uint64_t chunk_size)
    : sha256_(std::move(sha256)),
      size_(file_size),
      chunk_size_(chunk_size) {
    if (!IsDigest(sha256_) || size_ == 0 || chunk_size_ == 0)
        throw std::invalid_argument("Invalid immutable file identity");
    const auto count = size_ / chunk_size_ +
                       (size_ % chunk_size_ != 0 ? 1U : 0U);
    if (count > kMaxChunks)
        throw std::length_error("Too many chunks for journal");
    verified_.resize(static_cast<std::size_t>(count), 0);
}

void DownloadJournal::MarkVerifiedAfterFlush(std::size_t index) {
    if (index >= verified_.size())
        throw std::out_of_range("Chunk index out of range");
    verified_[index] = 1;
}

bool DownloadJournal::IsVerified(std::size_t index) const {
    if (index >= verified_.size())
        throw std::out_of_range("Chunk index out of range");
    return verified_[index] != 0;
}

std::size_t DownloadJournal::ChunkCount() const noexcept {
    return verified_.size();
}
std::uint64_t DownloadJournal::VerifiedBytes() const noexcept {
    std::uint64_t sum = 0;
    for (std::size_t i = 0; i < verified_.size(); ++i) {
        if (verified_[i]) {
            const auto position = static_cast<std::uint64_t>(i) * chunk_size_;
            sum += std::min(chunk_size_, size_ - position);
        }
    }
    return sum;
}

std::string DownloadJournal::Serialize() const {
    std::string output(kMagic, kMagicLen);
    output += sha256_;
    AppendU64(output, size_);
    AppendU64(output, chunk_size_);
    AppendU64(output, verified_.size());
    // Each bit refers to the corresponding fixed byte range; no duplicate files.
    for (std::size_t index = 0; index < verified_.size(); index += 8) {
        std::uint8_t bits = 0;
        for (std::size_t bit = 0; bit < 8 && index + bit < verified_.size(); ++bit) {
            if (verified_[index + bit])
                bits |= static_cast<std::uint8_t>(1U << bit);
        }
        output.push_back(static_cast<char>(bits));
    }
    const auto crc = Checksum(output);
    AppendU32(output, crc);
    return output;
}

DownloadJournal DownloadJournal::Deserialize(
    std::string_view contents, std::string_view expected_sha256,
    std::uint64_t expected_size, std::uint64_t expected_chunk_size) {
    DownloadJournal result(std::string(expected_sha256), expected_size,
                           expected_chunk_size);
    constexpr std::size_t fixed = kMagicLen + 64 + 8 + 8 + 8;
    const auto bitmap_len = (result.verified_.size() + 7) / 8;
    if (contents.size() != fixed + bitmap_len + 4 ||
        contents.substr(0, kMagicLen) != std::string_view(kMagic, kMagicLen)) {
        throw std::invalid_argument("Wrong or truncated journal");
    }
    if (contents.substr(kMagicLen, 64) != expected_sha256 ||
        ReadU64(contents, kMagicLen + 64) != expected_size ||
        ReadU64(contents, kMagicLen + 72) != expected_chunk_size ||
        ReadU64(contents, kMagicLen + 80) != result.verified_.size()) {
        throw std::invalid_argument("Journal belongs to a different PKG");
    }
    if (ReadU32(contents, contents.size() - 4) !=
        Checksum(contents.substr(0, contents.size() - 4))) {
        throw std::invalid_argument("Journal checksum mismatch");
    }
    for (std::size_t i = 0; i < result.verified_.size(); ++i) {
        const auto byte = static_cast<unsigned char>(contents[fixed + i / 8]);
        result.verified_[i] = (byte & static_cast<unsigned char>(1U << (i % 8))) ? 1 : 0;
    }
    if (result.verified_.size() % 8 != 0) {
        const auto last = static_cast<unsigned char>(
            contents[fixed + bitmap_len - 1]);
        if ((last >> (result.verified_.size() % 8)) != 0)
            throw std::invalid_argument("Non-canonical chunk bitmap");
    }
    return result;
}
}  // namespace odium
