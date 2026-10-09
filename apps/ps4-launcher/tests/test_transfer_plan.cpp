#include "odium/transfer_plan.hpp"
#include <cassert>
#include <cstdint>
#include <limits>
#include <stdexcept>
int main() {
    using odium::BuildTransferPlan;
    using odium::ValidateTransferPlan;
    const auto exact = BuildTransferPlan(32, 16);
    assert(exact.size() == 2);
    assert(exact[0].offset == 0 && exact[0].length == 16);
    assert(exact[1].offset == 16 && exact[1].length == 16);
    assert(ValidateTransferPlan(exact, 32));
    const auto tail = BuildTransferPlan(33, 16);
    assert(tail.size() == 3);
    assert(tail[2].offset == 32 && tail[2].length == 1);
    assert(ValidateTransferPlan(tail, 33));
    assert(!ValidateTransferPlan(tail, 34));
    assert(!ValidateTransferPlan({{0, 16}, {15, 17}}, 32));
    assert(!ValidateTransferPlan({{0, 16}, {17, 15}}, 32));
    assert(!ValidateTransferPlan({{0, 33}}, 32));
    bool throws = false;
    try { (void)BuildTransferPlan(32, 0); }
    catch (const std::invalid_argument&) { throws = true; }
    assert(throws);
    const std::uint64_t big = 100ULL * 1024 * 1024 * 1024;
    const auto big_plan = BuildTransferPlan(big, 64ULL * 1024 * 1024);
    assert(ValidateTransferPlan(big_plan, big));
    assert(big_plan.back().offset > std::numeric_limits<std::uint32_t>::max());
    return 0;
}
