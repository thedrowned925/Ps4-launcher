#include "odium/download_journal.hpp"

#include <cassert>
#include <stdexcept>
#include <string>
#include <vector>

int main() {
    const std::string digest(64, 'a');
    odium::DownloadJournal journal(digest, 33, 16);
    assert(journal.ChunkCount() == 3);
    assert(journal.VerifiedBytes() == 0);
    journal.MarkVerifiedAfterFlush(0);
    journal.MarkVerifiedAfterFlush(2);
    assert(journal.IsVerified(0));
    assert(!journal.IsVerified(1));
    assert(journal.VerifiedBytes() == 17);

    const std::string bytes = journal.Serialize();
    const auto restored = odium::DownloadJournal::Deserialize(bytes, digest, 33, 16);
    assert(restored.VerifiedBytes() == 17);
    assert(restored.IsVerified(0) && restored.IsVerified(2));

    auto fails = [&](std::string value, const std::string& name) {
        bool thrown = false;
        try {
            (void)odium::DownloadJournal::Deserialize(value, name, 33, 16);
        } catch (const std::invalid_argument&) {
            thrown = true;
        }
        assert(thrown);
    };
    auto corrupted = bytes;
    corrupted[corrupted.size() - 5] ^= 0x1;
    fails(corrupted, digest);
    fails(bytes.substr(0, bytes.size() - 1), digest);
    fails(bytes, std::string(64, 'b'));
    auto forged = bytes;
    forged[0] = 'X';
    fails(forged, digest);

    // No chunk can be marked without an in-range index.
    bool out_of_range = false;
    try { journal.MarkVerifiedAfterFlush(3); }
    catch (const std::out_of_range&) { out_of_range = true; }
    assert(out_of_range);
    return 0;
}
