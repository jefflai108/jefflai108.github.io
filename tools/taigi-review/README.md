# Taigi label correction

Public app shell: https://jefflai108.github.io/taigi-review/

Private API/audio origin: https://taigi-review-api.heymachi.live

Open the invitation URL with its `#key=...` fragment. The fragment stays in the browser; it is sent only as a bearer authorization header to the private review API. The Share review button copies the invitation for a co-annotator. Anyone holding that invitation can read recordings/transcripts and edit this shared review. Never commit or publicly post the invitation.

The plain URL and invitation URL use the same saved corrections and history. After a successful unlock, the browser remembers the key, so the plain URL works in that browser too. Adding the invitation fragment to an already-open page unlocks it without reloading, and other locked tabs pick up access through a storage event. A new browser/profile or private session still needs the invitation. Locked or loading pages show unknown progress rather than a misleading zero; failure to remember access is reported to the reviewer.

## Dataset and storage

Two review tabs use independently pinned splits from `jefflai108/streaming-taigi-asr`, config `default`:

| Tab | Split | Clips | HF revision | Manifest SHA256 |
| --- | --- | --- | --- | --- |
| Dev set review | `validation` | 5,424 | `6722261aee9c4d729b4c5bdd629ec3ebf2060179` | `9f676034bdaa564a554d93443dbf1836fc2782270cb1eb36b75679b27838c78d` |
| Dev2 set review | `validation2` | 5,133 | `7889df22aa03f5dd1805737d24c5d39729a60a54` | `0848a6246cb5d25a2ef7c8415416c87686cbd2df258d543e03794db4953daee0` |

Original transcripts and audio fingerprints were checked against their HF parquet shards. The initializer rejects changes to the pinned manifest or source identity. The private HF data is not bundled with the public website.

- Existing source: `~/streaming_taiwanese/evals/taigi_dev/manifest.jsonl` and `audio/`.
- Authoritative database: `~/Library/Application Support/Taigi Review/annotations.sqlite3`.
- Dev2 source: `~/Library/Application Support/Taigi Review/validation2/manifest.jsonl` and `audio/`.
- Dev2 database: `~/Library/Application Support/Taigi Review/annotations-dev2.sqlite3`. Its private config lives under the `dev2` object with `db_path` and `manifest` fields.
- Private config and invitation key: `~/Library/Application Support/Taigi Review/config.json` (0600).
- Runtime copies of server/backup code are alongside that config, so the service doesn't depend on a checkout remaining unchanged.
- Daily consistent SQLite snapshots: `~/Library/Application Support/Taigi Review/backups/`. These are backups, not a second editable review.

The original transcript is immutable. Human annotation initially equals the original. Saves use transactions and revision checks, with atomic append-only history. Concurrent conflicting edits require the annotator to compare both versions and choose explicitly. Empty transcripts are allowed for clips with no speech. Editing a reviewed transcript reopens its review status. Display names identify edits but are not independent authenticated identities.

The browser polls changes every three seconds and caches the current/next audio for quick replay. Device storage holds the invitation, display name, last clip, playback speed, and emergency unsaved drafts; server SQLite is the only authority. Failed saves remain visibly unsaved, block navigation and tab switching, and retain their base revision even across reopening. The UI warns before closing with pending changes. Export annotations downloads the selected review set, including originals, human annotations, review status, and source identity.

Dev2 shares the existing invitation key and reviewer name. Its routes are `/api/dev2/meta`, `/api/dev2/clips`, `/api/dev2/changes`, `/api/dev2/export`, and `/api/dev2/clips/{id}` with the same audio/history suffixes and revision-checked PUT contract. Existing `/api/...` Dev routes and all saved Dev edits remain compatible with already-open browsers. Review databases, progress, history, change cursors, drafts and last-clip bookmarks remain separate. Late responses from a previous set are ignored after switching. Both databases receive daily consistent backups.

To reconstruct Dev2 on another machine, authenticate with Hugging Face and run `prepare_dev2.py --out /private/path/validation2` using Python 3.11+ with `huggingface_hub` and `pyarrow`. It downloads only the two pinned validation2 shards, verifies shard and audio SHA256 values, validates WAV format and clip count, and publishes a new directory with a source receipt. It refuses to overwrite an existing directory or write beneath the repository's `public/` directory. Then configure the separate Dev2 database/manifest and start the server; do not reuse the Dev database path.

## Mac service operation

The app needs this Mac awake, online, and logged in. The existing Mac wake service remains unchanged. LaunchAgents restart the review server and its separate named Cloudflare tunnel automatically after login or process failure:

- `com.jefflai.taigi-review` — loopback-only HTTP server on `127.0.0.1:8766`.
- `com.jefflai.taigi-review-tunnel` — dedicated named tunnel `taigi-review`, config `~/.cloudflared/taigi-review.yml`.
- `com.jefflai.taigi-review-backup` — daily SQLite backup.

Logs: `~/Library/Logs/com.jefflai.taigi-review*.log`. No request paths, authorization headers, or transcript contents are logged by the app.

To apply a backend update, first take consistent backups, copy `server.py`, `recordings.py`, and `backup.py` to the runtime folder, then run `launchctl kickstart -k gui/$(id -u)/com.jefflai.taigi-review`. Do not delete or recreate either database. To rotate review access, generate a new random key in private config, restart the backend, and share the new invitation through a private channel.

The existing `machi` tunnel and website are separate. GitHub Pages serves the app shell through the repository's existing deploy workflow.

## Validation

Run from the repository root:

```sh
python3 -m unittest discover -s tools/taigi-review -p 'test_*.py' -v
node --test tools/taigi-review/test_frontend.mjs
node_modules/.bin/tsc --noEmit --target ES2022 --module ESNext --moduleResolution bundler --lib ES2022,DOM --skipLibCheck src/scripts/taigi-review.ts src/scripts/taigi-recordings.ts src/scripts/taigi-session.ts
npm run build
```

Tests use synthetic clips and isolated temporary storage. Public API verification checks authorization, CORS, exact WAV byte content, and source/count. Production labels are never modified for testing.

Optional WebMCP tools feature-detect support: `read_current_taigi_clip` and `save_taigi_annotation`. They reuse the visible editor and its conflict checks for the selected Dev or Dev2 set; reads identify the split. Contract tests cover registration and valid/invalid input; no supported live WebMCP browser context was available, so live browser registration was not verified.

The Dev2 addition was also checked in headless Chrome with two isolated reviewer sessions and synthetic data: saves remain in the selected split, a conflicting draft blocks tab switching, accepting the shared version permits navigation, all three tabs and keyboard navigation work, audio plays, and the 375px mobile layout has no horizontal overflow. Production save endpoints are not used for these tests.

## Record & annotate

The upper **Record & annotate** tab captures audio from each visitor's own microphone after they press Start recording and grant browser permission. Recordings are limited to two minutes. Visitors can replay or download a take, type its transcript, then save audio and transcript together. Saved transcripts autosave and use the same explicit conflict comparison as the dev review.

User recordings live in separate `recordings` and `recording_history` tables in the original database. They never join either HF review split or its export/progress. The separate recording export identifies its source as `user_recordings`. Audio uploads use a stable UUID and SHA256 to prevent duplicate takes or audio replacement on retry. Both original compressed audio and a normalized mono PCM16 16 kHz WAV are committed atomically with the recording and initial transcript; daily SQLite backups include both audio representations.

`recordings.py` uses the existing `/opt/homebrew/bin/ffmpeg` to validate/decode browser WebM, MP4, Ogg or WAV captures. It limits upload size, audio duration, decoder concurrency and processing time. New private routes are `POST /api/recordings`, `GET /api/recordings`, `GET/PUT /api/recordings/{id}`, plus `/audio`, `/history`, and `/api/recordings/export`. The invitation key is required for every route.

Unuploaded takes are kept in this browser's IndexedDB and appear as recoverable takes after reopening. This local recovery area is temporary; the shared database remains authoritative after upload. If local storage is unavailable or full, the page tells the visitor to keep it open and offers an audio download. Microphone tracks are released on stop, startup failure and page exit; a permission result arriving after the visitor leaves cannot start a hidden recording. The recorder stops when its page is hidden. No real microphone was activated during implementation; capture lifecycle and recovery tests use synthetic media, and server tests decode real generated WebM/MP4 files.

When updating the backend, copy **both** `server.py` and `recordings.py` to the private runtime directory before restarting the service. The schema extension is additive and preserves all existing dev annotations. Run the additional frontend tests with:

```sh
node --test tools/taigi-review/test_recording_frontend.mjs
```
