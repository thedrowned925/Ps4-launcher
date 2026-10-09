#include "odium/transfer_plan.hpp"
#include <algorithm>
#include <stdexcept>
namespace odium {
std::vector<Chunk> BuildTransferPlan(const std::uint64_t file_size,
                                     const std::uint64_t chunk_size) {
    if (file_size == 0 || chunk_size == 0) {
        throw std::invalid_argument("file_size and chunk_size must be positive");
    }
    constexpr std::uint64_t kMaxChunks = 1'000'000;
    const std::uint64_t count = file_size / chunk_size +
                                (file_size % chunk_size != 0 ? 1U : 0U);
    if (count > kMaxChunks) {
        throw std::length_error("too many chunks for an in-memory plan");
    }
    std::vector<Chunk> plan;
    plan.reserve(static_cast<std::size_t>(count));
    for (std::uint64_t position = 0; position < file_size;) {
        const std::uint64_t size = std::min(chunk_size, file_size - position);
        plan.push_back({position, size});
        position += size;
    }
    return plan;
}
bool ValidateTransferPlan(const std::vector<Chunk>& chunks,
                          const std::uint64_t file_size) noexcept {
    if (chunks.empty() || file_size == 0) return false;
    std::uint64_t next = 0;
    for (const auto& chunk : chunks) {
        if (chunk.offset != next || chunk.length == 0 ||
            chunk.length > file_size - next) return false;
        next += chunk.length;
    }
    return next == file_size;
}
}  // namespace odium
