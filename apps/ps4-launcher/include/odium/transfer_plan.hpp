#pragma once
#include <cstdint>
#include <vector>
namespace odium {
// Range in the FINAL temporary PKG file; no later merging step.
struct Chunk {
    std::uint64_t offset;
    std::uint64_t length;
};
std::vector<Chunk> BuildTransferPlan(std::uint64_t file_size,
                                     std::uint64_t chunk_size);
bool ValidateTransferPlan(const std::vector<Chunk>& chunks,
                          std::uint64_t file_size) noexcept;
}  // namespace odium
