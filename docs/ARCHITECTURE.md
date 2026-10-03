# Architecture

## Current Version

Current application version: **v0.5.1** — UI/UX refinement.
V0.5 Backend and Frontend are complete; the V0.5.1 presentation-only patch is
implemented, integrated into `main`, and released as the current stable version
`v0.5.1`. The real
database schema remains `0005_add_deadlines_recurrence_reminders`; V0.6
remains the next planned feature-development version. Release status is
confirmed by Git tags.

## Frozen V0.6 — Data Safety & Recovery

Status: Phase 1 Backup Core/Create/List/Verify/Manifest V1 are committed.
Phase 2 Maintenance UI is committed with rough manual visual acceptance.
Phase 3A maintenance lock/state tracking and Launcher/Backend startup blocking
prototypes are committed. Phase 3B read-only Restore Dry Run and RestorePlan
generation are committed. Phase 3C isolated-only execution is committed.
Phase 3D coordination and completed acknowledgement are implemented in the
working tree, pending Review. Production/real-database Restore and Reminder poll
visibility remain unimplemented. Isolated tests do not prove power-loss durability.
Stable release is `v0.5.1`. This version is not Statistics,
Review, AI, Task Organization, or a Notification Service.

### Product and Storage Boundaries

MVP includes Create/List/Verify Backup, Restore Dry Run, Pre-Restore Safety
Backup, offline Restore CLI, automatic post-Restore verification, and a
lightweight Maintenance view. NO DATABASE MIGRATION REQUIRED. Existing
`0005_add_deadlines_recurrence_reminders` and all business semantics stay intact.
Metadata, Restore logs, and maintenance state are controlled filesystem data,
Git ignored, never business tables. No `0006` is created.

### Backup and Verification

Maintenance UI uses the existing Hash navigation (`#maintenance`), with a
secondary 数据与备份 entry. It creates, lists and explicitly verifies registered
backups; no polling, deletion, Restore button or invented CLI command exists.
Current application/schema status comes from the read-only runtime endpoint,
not historical Backup metadata. List verification is labeled as a registration
record; measured verification results remain local to the current view. An
unverified compatible record says 需要验证, not currently safe to Restore.
Restore guidance explains offline overwrite risks and deferred Phase 3 work.

Default root is `data/backups/`. Use Python `sqlite3.Connection.backup()` with
a read-only source connection; include committed WAL data. Copying the active
main file is not a consistent backup mechanism. Backup captures an internally
consistent committed snapshot, not every write made before it finishes.

Publication order: unique temporary file → Online Backup → close target →
integrity check → foreign key check → schema/critical-structure check →
SHA-256 → publish database without overwrite → publish Manifest V1.
Incomplete artifacts are not recoverable entries. Published Backup databases
are immutable. No automatic Backup cleanup is included in V0.6.

Phase 1 uses atomic same-filesystem hard-link publication followed by removal
of the temporary link: existing final files cannot be overwritten. Files and
directory are fsynced before success. Backup ID is independent of filename.
Root derives from configured database parent / `backups`, never API input.
Descriptor walking with NOFOLLOW guards root components and regular-file opens.
Linux/WSL is the supported platform: SQLite inspection and temporary-target
writes use `/proc/self/fd` references to the held file, and publication links
that same inode rather than reopening a replaceable pathname. Unsupported
descriptor/hard-link facilities fail closed; there is no pathname fallback.
Published input files must have one link. Publication briefly adds a second
link only to the verified temporary inode, then removes the temporary name.
Verification rechecks identity, timestamps and SHA after inspection. These
guards do not provide authenticity against a user who controls the same OS
account and can rewrite both Backup and Manifest.
Online Backup is bounded (10-second limit, short SQLite busy timeout), with
no Maintenance lock. Concurrent creators use independent UUIDs and exclusive
temporary files. Manifest publication failure retains the DB as an unlisted
orphan and returns registration failure, never success.

Verify is explicit and read-only; it checks readability, SQLite format, hash,
size, integrity, foreign keys, Alembic version, required DayFlow tables, and
critical structure. Manifest is metadata, not truth. List displays last known
verification and timestamp; it does not silently perform full verification.
Structural checks derive required columns, PKs, FKs, CHECK expressions and
indexes from current models, plus the Alembic version table PK. They are a
compatibility screen, not a second Migration engine or proof of arbitrary SQL
semantic equivalence; no Backup is migrated or repaired during verification.
Recovery of missing Metadata requires separate explicit registration.

Create stores first verification time in Manifest. Subsequent Verify returns
its own timestamp and never edits published artifacts. Phase 1 skips invalid
registrations (logged); registration/rebuilding remains deferred explicit
maintenance. See `docs/API.md` for implemented result/error contracts.

Only exact schema `0005_add_deadlines_recurrence_reminders` is restorable.
Old, unknown, and newer versions may be inspected but cannot be restored.
Restore never migrates. Verification distinguishes valid-compatible,
valid-incompatible, corrupted, missing/unreadable, and Manifest mismatch as
semantic categories; these strings are not frozen API enums.

### Offline Restore Workflow

1. Verify target and show summary (identity, schema, hash, counts, overwrite impact).
2. Obtain explicit confirmation and maintenance lock.
3. Stop only identity-validated, managed DayFlow services.
4. Confirm database usage state; unknown processes or uncertainty fail closed.
5. Create and verify current database Pre-Restore Safety Backup.
6. Verify target again; build an independent Restore candidate and verify it.
7. Close all connections, persist candidate/operation state, perform controlled switch.
8. Verify final integrity, foreign keys, Alembic version, structure, and data.
9. Record result; leave services stopped and blocking marker retained until
   explicit, verified completion acknowledgement. Success alone does not unlock.

Running Backend cannot replace its active database. Restore is Maintenance CLI
only; HTTP UI offers summary/explanation and prepared CLI guidance, not an
active-database replacement button or automatic shutdown worker.

Original DB/WAL/SHM material must be preserved in a controlled recovery
location before switching. Old WAL must never attach to the restored database.
Preserve original material, target, Pre-Restore Backup, candidate, and log until
a human decides retention. Source Backup is never consumed or modified.
Any failure stops further steps; never automatically rollback, downgrade, guess
recovery, or start services. No automatic service startup after success either.

### Maintenance and Startup Boundary

#### Phase 3A implemented prototype (not Restore)

`app.core.maintenance` operates only on controlled filesystem state in the
configured database's sibling `maintenance/` directory (default
`data/maintenance/`, Git ignored). It never opens SQLite, creates Backup data,
copies a Restore source, switches DB/WAL/SHM, stops a process or runs migrations.
There is no HTTP maintenance mutation or actual Restore CLI. The read-only
Launcher preflight remains `python -m app.core.maintenance --check`.

Two independent protections are required:

- A persistent `maintenance.lock` acquisition record contains UUID4 `lock_id`,
  UTC `created_at_utc`, `operation=restore-safety-prototype`, acquisition stage
  `prepare`, format version and application version. `restore-state.json`
  carries the matching identity and current stage. PID is not authority.
- A permanent `coordination.lock` inode uses nonblocking Linux/WSL `flock`.
  Backend ASGI lifespan checks state while holding a shared lease, retained
  for its lifetime. Prototype begin/transition/cleanup require an exclusive
  lease. Thus begin refuses while a cooperating Backend is running, without
  trying to stop it; Backend refuses to start after begin. The Launcher checks
  before its first SQLite open or process handling; Backend checks again to
  close the preflight/start race. The stop script is unchanged.

The coordination inode is never removed/replaced. State publication uses an
exclusive temporary file, file fsync, no-overwrite hard-link publication for
the acquisition record, atomic state-file replacement, and directory fsync.
Directory-descriptor walking and NOFOLLOW reject symlinks; nonregular files,
hard-linked records, foreign ownership, unsafe write permissions, unknown
files/partials, unknown formats/stages and parse failures block startup.
No insecure platform fallback is provided. State checks never silently remove
or repair artifacts. Empty/missing state is implicit `idle` (no write).

Normal simulated transitions are:

`idle → prepare → verified → switching → verifying → completed`

Each active stage may instead enter terminal `failed` or `blocked`. Updates
require the matching lock ID and expected previous stage; skipped/backward or
stale transitions fail without mutation. Recording `completed` needs explicit
confirmation; it proves only completion of the state simulation, **not** actual
database verification. Startup remains blocked until a second explicit,
identity-checked cleanup removes the completed acquisition marker. Completed
state and coordination inode remain. Failed/blocked/corrupt/incomplete records
cannot be cleared by this prototype; no reset/unlock/recovery CLI is exposed.
A persisted `idle` record is not an escape hatch and is rejected at startup.

Tests use isolated directories and actual child-process abnormal exits at
prepare/switching/verifying. The next Launcher/Backend check must reject them
without automatic continuation, rollback or record deletion. Tests also cover
concurrent acquisition, cross-process usage leases, corrupt/missing records,
publication/flush failure, explicit cleanup and absence of DB creation.

Limits: this is a cooperative Linux/WSL protocol, not a detector for arbitrary
SQLite connections or pre-existing Backend versions. Bypassing ASGI lifespan
is unsupported. Same-account actors able to rewrite controlled files are not
an authenticity boundary. Databases sharing a parent conservatively share the
maintenance root. Actual DB connection draining, unknown-process inspection,
DB/WAL/SHM preservation and switching/crash durability tests remain future
Phase 3 gates. Phase 3A authorizes no real Restore and no production unlock.

#### Remaining Phase 3 requirements

#### Phase 3B implemented prototype (Dry Run only)

`python -m app.maintenance_cli restore --dry-run <backup_id>` reads the
current database and invokes the existing read-only Backup Verify service. It
returns a `RestorePlan` containing current/target metadata, exact Schema
compatibility, the future Restore steps, and explicit refusal reasons. The
human-readable output includes `No changes performed.`; `--json` returns the
same plan as JSON.

This prototype never acquires `maintenance.lock`, writes `restore-state.json`,
creates a Backup, copies or replaces a database/WAL/SHM file, runs a migration,
stops a service, or changes a Manifest. It fails closed for an unreadable or
incompatible current database or target Backup. A non-zero exit means no
Restore action was performed. Actual Restore integration, candidate switching,
and recovery execution remain out of scope.

Maintenance CLI, start script, and Backend startup must coordinate database
usage locks, maintenance lock, and durable incomplete-Restore marker. Port
checks alone are insufficient. The existing startup operation lock is not a
database lifetime/maintenance protocol; Phase 3A adds cooperative safety state,
while actual database-use verification remains deferred.
Both script-mediated and direct Backend startup must refuse normal operation
while maintenance is active or a Restore is incomplete. Lock design must permit
managed shutdown without deadlocking the stop script.

File switching is not a SQLite transaction: durable phase records, disk flushes,
and startup blocking must cover process interruption and partial switching.
Specific locking/switching mechanics are deferred to isolated Phase 3 prototypes:
(1) SQLite connection/process usage/maintenance coordination; (2) DB/WAL/SHM
crash points, retained artifacts, startup blocking, and recovery inspection.
These do not block Phase 1; they block any real Restore pending tests and
separate explicit user approval. Development Restore is isolated only.

### Phase 3C Frozen Restore Execution Protocol (Isolated Prototype Implemented)

`app.services.restore_service` executes only against canonical independent
databases beneath the system temporary directory, never the project's `data/`
tree. The temporary root must resolve to `/tmp` or `/var/tmp`; an environment
override cannot expand that boundary. Protected DB and directory inode aliases
are rejected in addition to canonical paths and single-link/NOFOLLOW checks.
Roots derive from the source parent; no destination/path/force flag exists.
`python -m app.maintenance_cli restore <backup_id>` requires stdin/stdout TTY and
exact `RESTORE <UUID4>` confirmation. Actual execution rejects `--json`; Dry Run
and its JSON contract remain unchanged. Execution never starts/stops services.
The offline operator must stop them first. Completed execution remains blocked
until the Phase 3D explicit, reverified acknowledgement described below.

The implementation adds a lifetime exclusive coordination lease and explicit
V2 `restore` records without changing business APIs or migrations. Current DB
checks use private admission copies; after admission, durable evidence/master
and working copies are retained. Safety Backup uses existing Online Backup
core against the captured quiescent current working set. Raw copies are evidence,
not registered backups. Candidate and install copy are separate verified inodes.
Final verification includes exact bytes and typed, PK-ordered logical hashes of
all core persisted columns, never plaintext row contents in logs.
The confirmation summary binds both target and Manifest inode/hash receipts,
not just the target SHA. Standalone logical inspection uses held descriptors;
archive receipts recheck the moved inode/bytes before any install. V2 completed
state itself remains blocking even if its acquisition marker is removed.

Internal optional test hooks cover C0-C9 and C5a/C5b/C5c; there is no API/env crash
switch. Tests use a controlled fully visible process view plus real child file/
SQLite holders and explicit permission/unavailable-proc refusal tests. Production
always inspects `/proc`; inaccessible host processes cause refusal, not fallback.
Same-account racing/noncooperative actors and hidden namespaces remain outside
the cooperative guarantee. Phase 3D must validate actual process visibility,
Launcher preflight-to-Backend lease handoff, connection disposal and real storage
durability before any separate real Restore approval. No real Backup/Restore
smoke was performed in Phase 3C.

This is an offline Linux/WSL design, not real Restore authorization.
Phase 3B remains Dry Run only. Dry Run is neither an authorization token nor a
substitute for fresh checks. No new business API, Schema, dependency or state
stage is required. Real Restore remains prohibited during development.

#### Preconditions and Lock Ownership

Before admission: require canonical UUID4, registered target, fresh
`BackupService.verify()` result `valid`, matching Manifest and exact compatible
`0005_add_deadlines_recurrence_reminders`; explicit operator confirmation;
supported filesystem and process visibility; no unresolved previous operation.
The operator must first stop DayFlow using the existing protected stop workflow.
An active Backend is a refusal, not an invitation to terminate it automatically.
The workflow's managed-service-stop step is an idempotent check that shutdown
has completed; any remaining managed service or ambiguous identity rejects it.
This preserves the existing prototype's refusal to acquire while Backend runs.
No unknown process is terminated, and no port/PID check is authoritative.

Freeze the existing database-parent `maintenance/coordination.lock` as the
permanent cooperative lock inode. Same owner, mode 0600, regular single-link
file, safe directory descriptors/NOFOLLOW, no unlink/replacement or insecure
fallback. Backend takes nonblocking shared `flock` before any SQLite access;
it keeps the lease until request/session draining, pooled connection disposal
and shutdown are complete. Every cooperating database tool must use this gate.
Restore takes nonblocking exclusive `flock` and retains its descriptor for the
**whole operation**, including final verification and completion recording.
An occupied gate fails without acquiring a persistent maintenance marker.
PID/start time are diagnostic only. OS lease release after death does not clear
the durable marker. Current per-method prototype leases must be extended to a
single operation context; nested independent exclusive acquisitions are forbidden.

Phase 3D holds a shared gate throughout the Launcher's SQLite preflight.
The Backend independently checks state, acquires its shared gate, rechecks
state and only then initializes its database lifetime. No descriptor inheritance
is needed: an exclusive Restore acquired in the handoff gap refuses Backend
startup before DB access; completed/failed operations keep durable blockers.
This finalizes handoff safety without treating Launcher as the authoritative
barrier. If the existing
start/stop serialization lock is needed, acquire it before the coordination
gate in both paths; never invoke the stop script while holding that same lock.
No new process may inherit a maintenance descriptor. Freeze execution records
as format version 2, operation `restore`, retaining the current UUID `lock_id`
as operation/workspace identity and the existing timestamp/app-version/stage
fields. Detailed receipts live in the operation workspace. Readers explicitly
recognize prototype V1 and execution V2; all other format/operation combinations
block. Prototype `completed` is not proof of real verification.

Under the exclusive lease, reject a marker, malformed/unknown/partial state or
unacknowledged previous operation. Atomically publish a UUID-owned acquisition
record and `prepare` state, fsync both and their directory before preparation.
If only the acquisition record persists, startup still blocks. C0 means durable
marker admission, not merely acquiring the ephemeral OS lease. A crash before
any admission artifact exists has changed no database and admitted no operation;
it cannot leave an OS lock after process death. No preparation or switch is
allowed in that gap. Before switching,
also require current readable/compatible structure, integrity `ok`, FK errors 0,
verified Safety Backup and candidate, and no unresolved usage uncertainty.

#### External SQLite Users and Supported Environment

`flock` is authoritative only for cooperative DayFlow processes. Inspect Linux
`/proc` descriptors and file mappings for the current DB/WAL/SHM device/inode
identities and their resolved names, including deleted/renamed references.
Exclude only this operation's explicitly owned descriptors; `lsof`/`fuser`/ports
are optional diagnostics, never substitutes. Rescan after preparation and just
before the first move. Process disappearance may be retried with a bounded
deadline; inaccessible relevant processes, hidden namespaces, permission errors,
ambiguous references, or a detected user fail closed. No warning-and-continue
override. Read/write users and IDE viewers are treated alike.

A scan cannot prevent a noncooperative process from opening a file immediately
afterward. Supported operation therefore additionally requires a quiescent local
environment and operator confirmation that external tools are closed and remain
closed. Same-account malicious actors and unobservable external namespaces are
not covered by an authenticity guarantee. An environment where visibility cannot
be established is unsupported, even if this makes Restore unavailable. Never
claim that flock or a clean scan proves universal SQLite exclusivity.

#### Workspace, Current Evidence and Safety Backup

Use database-parent `backups/restore-operations/<operation-UUID4>/`, created once
with exclusive semantics, directories 0700/files 0600. Never reuse/overwrite an
operation. It is already Git ignored; top-level Backup List ignores directories.
Keep `maintenance/`'s strict entry allowlist unchanged. Internal paths are
descriptor-derived; no API/CLI user pathname or Manifest filename is trusted.

Workspace contains `operation.json`, `events.jsonl`, verification receipts,
`current-evidence/`, private `current-working/`, `pre-restore-safety/`, `original/`, immutable
`candidate.sqlite3`, and independent `install.sqlite3.partial`. The maintenance
record UUID identifies the workspace; logs contain controlled relative names.
Admission creates and fsyncs the blocking marker before these artifacts.

After usage checks, inventory DB/WAL/SHM existence, inode, size and hash. Preserve
a quiescent raw evidence copy before any SQLite inspection. This is **not** a
backup: it is forensic input, never registered/listed/restorable on its own.
Copy each held regular single-link descriptor into private `current-evidence/`
under its original basename; check source identities/hashes again after capture.
Any drift fails closed. An unexpected rollback journal is a refusal, not an
invitation to recover/erase it. Record explicit absence of each sidecar.

SQLite read-only WAL access can use/update shared-memory bookkeeping. Therefore
perform logical current checks and Online Backup against a private working copy
of the captured evidence set, not the live names or immutable evidence master.
Do not use `immutable=1` to inspect a WAL-bearing current database: it would
ignore the live transaction context. Do not checkpoint, VACUUM, ANALYZE, change
journal mode, migrate or repair the original. Recheck live DB/WAL/SHM identity and
bytes before switching; preserve initial evidence even if private SQLite working
sidecars change. Unknown/recovery-needed source conditions reject preparation.

Create Safety Backup with the Phase 1 Online Backup/verification/publication
core from that quiescent current working set, including committed WAL and
excluding uncommitted data. Raw evidence copying never substitutes for this
step. Its controlled directory `pre-restore-safety/` distinguishes purpose while
retaining existing `dayflow-backup-...sqlite3` naming and Manifest V1. Record
purpose and Safety Backup ID in operation metadata, not a new business table.
Require published DB plus Manifest, clean integrity/FK/current structure, SHA,
size and matching logical current contents. Compare all persisted core columns
using type-preserving deterministic streams ordered by primary key, including
soft-deleted rows and association tables, plus counts. Only digests/counts may
enter verification receipts, never row contents; isolated tests also compare
actual values. Counts alone are insufficient. Any failure prohibits switching.

#### Target and Candidate Identity

Reverify the registered target after Safety Backup. Reuse Backup Verify and its
structural screen; bind the selected Manifest and held NOFOLLOW database
descriptor to UUID, inode, size and SHA. Reject sidecars, replacement or metadata
drift. Copy **only this verified standalone immutable target**, using bounded
descriptor reads and O_EXCL destinations, into an independent candidate inode.
Close/fsync it, then perform fresh read-only integrity/FK/schema/structure checks
and hash/size comparison. Preserve target and Manifest unchanged permanently.

Online Backup is mandatory for a WAL-bearing current source. For the already
standalone target, exact safe byte copying is chosen over Online Backup: it
preserves physical SHA identity and avoids page-layout changes. Never use a
hard link as a candidate; otherwise later live writes could mutate the retained
source. Prepare a second independent install file from candidate, verify it and
fsync it. Candidate master remains available even after installation consumes
the install name. Record target = candidate = install SHA and size.

Logical equivalence means the same schema and all persisted table values,
including IDs, versions, deleted records and relationships, not merely equal
counts. Exact bytes establish this for the chosen target-copy method; counts
are supplementary diagnostics. Safety Backup produced by Online Backup may
have a different physical SHA from the current main DB while preserving the
committed logical snapshot. Never compare it to main-file SHA as a validity test.

#### Controlled Switch and Durability

Initially support a tested local Linux/WSL ext4 filesystem. Live directory,
workspace and install file must be on the same mounted filesystem; reject
DrvFS (`/mnt/c`), network/FUSE/unvalidated filesystems and cross-mount switching.
Before any move, require tested directory fsync and Linux
`renameat2(RENAME_NOREPLACE)` support. No check-then-overwriting `os.rename`,
copy/unlink cross-device fallback, or live-database `os.replace` is allowed.
State JSON alone uses exclusive temporary write → file fsync → atomic replace
→ directory fsync. Phase 3 implementation must centrally encapsulate and test
the no-replace syscall; unsupported capability refuses execution.

1. Close every SQLite connection and preparation descriptor not needed for
   identity checks; repeat usage/content checks. Verify Safety Backup, candidate,
   independent install file, original inventory and operation receipt are durable.
2. Persist `verified`; write switch intent (source/destination identities and
   sidecar inventory). Persist `switching` and fsync before the first live move.
3. Archive existing WAL, then SHM, then main DB into `original/`, keeping exact
   basenames. Before each move fsync the held original file and persist intent;
   use no-replace rename by directory descriptor, then fsync **both** source and
   destination directories and persist the completion receipt. An absent sidecar
   is a recorded skip; an unexpected new file/identity is failure.
4. Confirm all three live names are absent. Rename independent install file to
   the live main filename with NOREPLACE; fsync installed file and both affected
   directories, then persist installation receipt. Do not create old sidecars
   or change SQLite journal mode. Candidate master remains in the workspace.
5. Persist `verifying`; re-open the installed, standalone main file read-only,
   immutable, bound to its held descriptor. Run final verification and rehash;
   any unexpected sidecar or inode/content change rejects completion.
6. Close connections, fsync final verification receipt/result log and live file/
   directories. Persist `completed` only after all guarantees pass. Leave
   services stopped and acquisition marker retained. Release OS leases on exit.

The three original names do not move atomically as a group. Sidecars-first keeps
the main filename absent before installation but briefly leaves the old main
without its WAL: the durable blocker makes this **not runnable**. A mixed archive
after interruption is evidence, not permission to open either DB normally.
Every action has a durable intent before and receipt after. If the receipt is
missing, inspect both names/inodes/hashes manually; never infer success from a
stage string or auto-resume. An fsync failure is an uncertain result even if a
rename returned success. No filesystem protocol promises immunity to faulty
hardware or storage that dishonors flushes.

#### State Guarantees and Crash Matrix

No new stages: implicit `idle` means no active marker; `prepare` guarantees the
admission marker is durable; `verified` guarantees safety/candidate/preconditions;
`switching` guarantees durable switch intent before any move; `verifying`
guarantees installed file and archive receipts are durable; `completed` guarantees
final verified result and receipts. `failed` means a known error; `blocked` means
usage/durability/artifact uncertainty. Both retain the marker. Failed state
publication leaves the last durable state/marker/partial in place; never erase
it or fabricate completed. Match operation ID and expected previous stage.

In the matrix, T is unchanged registered target, S is verified Safety Backup,
C is retained candidate master, I is the separate install file. Original evidence
is additionally retained once captured. Partial artifacts are retained too.

| Crash | Live main | Original DB / WAL / SHM | Candidate / install | T / S | Durable state; startup |
| --- | --- | --- | --- | --- | --- |
| C0 admission marker acquired | old | live, unchanged | absent | T / absent | prepare, or marker-only; blocked |
| C1 safety published | old | live + evidence copy | absent | T / S | prepare; blocked |
| C2 target reverified | old | live + evidence copy | absent/partial | T / S | prepare; blocked |
| C3 candidates verified | old | live + evidence copy | C + I | T / S | prepare/verified; blocked |
| C4 switch state persisted | old | live; individual moves may next start | C + I | T / S | switching; blocked |
| C5 originals moved, before install | absent | original/; earlier subcrashes split live/archive | C + I | T / S | switching; blocked |
| C6 installed before verifying | new (or install rename not durable) | original/ | C; I consumed or location uncertain | T / S | switching; blocked |
| C7 verifying | new | original/ | C; I consumed | T / S | verifying; blocked |
| C8 final verified before completed | new | original/ | C; I consumed | T / S | verifying; blocked |
| C9 completed durable | new, verified | original/ | C; I consumed | T / S | completed + marker; blocked until explicit acknowledgement |

C0-C8 never auto-start, rollback, resume or delete artifacts. C9 also does not
auto-start/auto-clean; a separate explicit completion acknowledgement rechecks
identity, final receipts and final DB under exclusive lease, then removes only
the matching acquisition marker and active state with directory fsync, after
archiving their contents in the retained operation workspace.
Existing prototype cleanup must not accept real execution solely on `completed`.

#### Final Verification, Logs and Failure Policy

Final verification requires SQLite readable, full integrity `ok`, FK errors 0,
single exact Alembic version, required tables/columns/PK/FK/CHECK/index screen,
all core table counts equal to target, and physical SHA/size equal to candidate
and target before/after inspection. No migration/repair or business mutation.
Log `operation_id`, UTC timestamps, Backup/Safety IDs, controlled artifact names,
current main and WAL hashes, target/candidate/final hashes, stages, verification
results and safe failure codes in JSON/JSONL. No row values, titles, descriptions,
Project contents, token, secret, traceback or arbitrary absolute paths. DB
artifacts themselves remain private personal data. State/receipts are durable
authority for recovery inspection; a partial JSONL tail never authorizes startup.

| Failure | Live replacement | Startup / retained evidence |
| --- | --- | --- |
| invalid target/confirmation, busy cooperative lock | none | no new marker; pre-existing blockers untouched |
| external user/uncertainty before admission | none | refuse; no permission to proceed |
| usage uncertainty after admission; safety failure | none | blocked/failed marker; current and any partial safety/evidence/log retained |
| target reverify, candidate creation/verification failure | none | failed marker; T/S/partial C/evidence/log retained |
| original move failure | absent/partial archive possible | blocked marker; every remaining live and archived artifact retained |
| install failure | old absent; new may be installed if durability uncertain | blocked marker; archive/C/I/T/S/receipts retained |
| final verification failure | new installed | failed/blocked marker; all artifacts retained |
| state write/fsync/disk-full/permission error | depends on last action | stop immediately; last durable marker/state and partials retained |

After admission, failures never permit normal startup even when the old DB
remains intact. No automatic rollback, retry, fallback or cleanup. Manual
inspection must reconcile intent/receipts and artifacts before any new operation;
never rerun an operation UUID or overwrite an unresolved state. Real recovery
or clearing failed blockers requires separate explicit approval and a validated
recovery procedure, not a force flag in the execution prototype.

#### Confirmation, Cleanup and Implementation Gates

Future `python -m app.maintenance_cli restore <backup_id>` defaults to TTY-only
confirmation after a fresh summary of current/target identities, counts and
overwrite impact. Require typing `RESTORE <canonical-backup-id>`; cancellation,
EOF and non-TTY execution refuse before admission. V0.6 first implementation
has no `--yes`/`--force` bypass; any future noninteractive authorization requires
a separately frozen exact-ID/expected-hash contract. JSON output is not consent.
Execution prototype now accepts the confirmed isolated form without `--dry-run`;
the Dry Run parser and output contract remain available.

All marker presence, prepare/verified/switching/verifying/failed/blocked, unknown
format/state, partial records and gate contention block Launcher and direct
Backend startup. Completed is not automatically ignored while its marker exists.
After explicit verified acknowledgement, startup may proceed; completed state
is archived rather than retained as an active blocker. No service restarts
automatically. Original archive, sidecars,
evidence, T/S/C, logs and receipts have no V0.6 automatic cleanup; future manual
retention must not remove unresolved operations or the coordination inode.

#### Phase 3D Recovery Coordination (Implemented, Pending Review)

Backend owns the shared coordination lease for its whole ASGI lifespan.
Uvicorn drains requests before lifespan shutdown; tracked application Sessions
are closed and the SQLAlchemy pool is disposed before releasing the lease.
New Sessions are refused once shutdown begins. A resource-shutdown failure
publishes a blocking `shutdown.failed` record; no automatic cleanup is allowed.
Launcher protects its SQLite preflight with a separate shared lease and Backend
repeats all admission checks. Ordinary startup does not require Restore storage
qualification. Stop remains precise and unchanged.

`python -m app.maintenance_cli acknowledge <operation-id>` accepts only exact
canonical UUID4, dual TTY, and `ACKNOWLEDGE <operation-id>` confirmation.
Only matching V2 completed Restore records qualify. Under a lifetime exclusive
gate, re-read operation/result/final receipts, verify live SHA/size, exact 0005,
integrity/FK/critical structure, typed logical fingerprint, retained candidate,
absence of sidecars, and external-use visibility. V1, incomplete, corrupt or
unknown records cannot be acknowledged. Real project data remains rejected.

Acknowledgement uses a two-phase commit protocol. Phase A appends and fsyncs the
verified decision, writes an immutable `startup-clearance.json` into the operation
workspace, publishes a byte-identical no-overwrite mirror in the maintenance
directory, fsyncs both files/directories, and re-validates the complete receipt
while the active acquisition/completed blockers still exist. The receipt binds
the operation/Backup IDs, archived active records, live SHA/size/schema/logical
fingerprint, final-verification identity, exact confirmation identity and the
immutable operation-log digest. This durable, validated receipt is the sole
acknowledgement commit point.

Only after that commit may Phase B remove the active acquisition marker and
restore state, with a directory fsync after each removal. Cleanup is post-commit
housekeeping: a remaining or reappearing blocker still blocks startup. If all
blockers are absent, Launcher and Backend may start only after independently
validating both receipt copies, operation/final evidence and the current live DB.
Missing, malformed, mismatched or unreadable clearance evidence fails closed.
Retained Restore workspaces without a matching durable receipt also fail closed;
absence of active markers alone is never startup clearance.
No compensation/recreated guard is used as a safety prerequisite; a final
cleanup-fsync error cannot erase the already durable startup authority.
Interrupted pre-commit acknowledgements retain active blockers for manual
inspection, not automatic resume.
No Target/Safety Backup, candidate, original DB/WAL/SHM, workspace or log is
removed. No service is started. Catastrophic storage failure that prevents even
writing the clearance commit retains the pre-existing blockers; syscall probes cannot prove
power-loss durability or repair failed hardware.

`status --json` inspects metadata without creating directories or authorizing
cleanup. `storage-check --json` inspects opened directory mount identities and
ext4 support, then probes no-replace rename/collision, file/directory fsync and
flock exclusion in disposable system-temp files on that same mount. It never
creates probes inside requested data/backup directories. Unknown/DrvFS/other
unqualified mounts, cross-mount probes or unavailable mechanisms fail closed.
Qualification reports `real_restore_approved=false`: it is not a real Restore
authorization or storage power-loss certification. Execution/acknowledgement
remain restricted to independent system-temp databases.

Phase 3C execution tests must use disposable DBs/directories and subprocesses:
success; shared lease held; duplicate maintenance; unknown/inaccessible external
user; safety/target-reverify/candidate failures; candidate corruption; committed
WAL and existing SHM; no stale sidecar attachment; source evidence unchanged;
crashes C0-C9 and between each artifact move/intent/receipt/fsync; final verify,
state write, fsync, disk-full, permission and no-replace conflict failures;
unsupported filesystem; target/S/C/original preservation; unknown state; explicit
completed acknowledgement; no automatic restart/rollback; startup refusal.
Phase 3D validates Launcher lease handoff, orderly Backend connection disposal,
precise stop and the full DB/WAL/SHM crash protocol. Tests must establish both
logical WAL recovery and physical target/candidate/final identity. Process-kill
tests are not proof of power-loss durability: filesystem capability/durability
assumptions must be documented and validated before any real Restore approval.

Technical references: [Linux flock](https://man7.org/linux/man-pages/man2/flock.2.html),
[rename / NOREPLACE](https://man7.org/linux/man-pages/man2/rename.2.html),
[file and directory fsync](https://man7.org/linux/man-pages/man2/fsync.2.html),
[SQLite WAL file lifecycle](https://www.sqlite.org/walformat.html), and
[SQLite URI / immutable behavior](https://www.sqlite.org/uri.html).

### Maintenance UI and Ancillary Reminder Work

Continue Hash navigation with `#maintenance`, Chinese entry 数据与备份.
Show current database status, Create, List, Verify, Restore summary and CLI
guidance. Restore uses destructive-action styling and explicit confirmation;
incompatible entries show reasons and no executable Restore command.
No Router or unrelated UI redesign.

Reminder maintenance is limited to visible but restrained polling failure,
Retry, and clearing the error after recovery. Preserve 45-second polling,
session deduplication, ack/dismiss, and existing persistence. No Snooze,
History, OS Notification, Background Service, or schema changes. Remove this
item from V0.6 if implementation would expand scope.

### Failures, Paths, and Logging

Fail closed for Backup/Verify/Pre-Restore Backup failure, unknown database
usage, Manifest failure, disk full, permissions, timeout, candidate/final
verification failure, and interrupted Restore. Preconditions failing must
never replace current DB. Failures during/after switching leave a durable
startup-blocking marker. Logs contain stages, file identifiers, hashes,
verification results, and errors, never personal Task contents or secrets.

API accepts Backup IDs, never arbitrary paths. Root is controlled; reject
absolute input paths, `..`, traversal, symlinks, outside-root resolved paths,
non-regular files, and unexpected overwrite. Manifest filename is untrusted.
Only DayFlow-named, verified/registered files become Restore candidates.
Prevent target replacement between validation/use and match candidate content
to verified source. Mutating local API operations validate browser request
origin; Single User does not justify unrestricted filesystem access.

### Implementation and Acceptance Gates

Each phase has independent Review, Tests, Commit: documentation maintenance;
Phase 0 architecture; Phase 1 Backup Core/API; Phase 2 Maintenance UI;
Phase 3 Restore CLI/locks/Launcher/crash safety; Phase 4 small Reminder item;
Phase 5 full acceptance; Release Gate. Planned functionality must remain
distinguished from implemented functionality in release documentation.

All destructive tests use isolated temporary databases. Compare real database
SHA-256 before/after automation; it remains at `0005`. Full matrix:

| Area | Required coverage |
| --- | --- |
| Create | normal, active WAL, committed concurrent writes, timeout, permission failure, simulated disk failure |
| Metadata | SHA, size, Manifest, missing/damaged Manifest, mismatch |
| List | valid, incomplete, unknown files, stable ordering |
| Verify | valid, corrupted, incompatible, missing, unreadable, no Backup mutation |
| Path | traversal, absolute input, symlink, outside root, overwrite conflict |
| Preparation | dry-run, incompatible schema, unknown process, failed Safety Backup |
| Restore | isolated success, WAL isolation, preserve original/target/Safety Backup |
| Failure | before/during/after switch, interrupted process, startup-blocking marker |
| Launcher | normal start, incomplete Restore blocks start, precise stop |
| Reminder | poll failure, Retry, recovery, no implicit Reminder mutation |
| Regression | Backend, Vitest, existing 28 Playwright scenarios, type-check, build |

Acceptance includes approved real Backup smoke (no Restore) and disposable-copy
Restore. Real Restore always requires separate explicit approval.

Excluded: Review/Statistics, Saved Views, Manual Ordering, Kanban, AI, Cloud
Sync, Multi User, Mobile App, External Calendar, Project Hierarchy, Reminder
Background Service, Repeat Time Block, unrelated bundle/Starlette warnings,
large TaskEditor extraction, global CSS/API Client refactoring.

## Existing Application Architecture

DayFlow is a local-first, single-user modular monolith:

```text
Vue 3 Frontend → FastAPI REST API → Service Layer → SQLAlchemy → SQLite
```

The application is intentionally not split into microservices. AI, reminders,
recurrence, external calendar integration, and scheduling automation remain
outside V0.3 and V0.4. Project support is limited to the frozen V0.4 design
below; it must not be implemented as part of unrelated work.

The request path remains:

```text
HTTP route → Pydantic schema → Service Layer → SQLAlchemy Session → SQLite
```

Routes expose HTTP contracts only. Services own validation that depends on
stored data, state transitions, conflict detection, optimistic version checks,
and transaction boundaries.

## Existing Decisions

- SQLite is sufficient for the current single-user local workload.
- Synchronous SQLAlchemy is preferred for simple SQLite transactions.
- API version prefix is `/api/v1`.
- Real data lives under `data/` and is excluded from Git.
- Schema changes use Alembic only.
- Tests use isolated temporary databases.
- Timestamps are UTC instants; date-only planning uses `planned_date`.
- UUIDs are generated by the application and stored as text for SQLite portability.
- V0.1/V0.2 statuses remain `pending` and `completed`.
- Soft deletion is represented by `deleted_at_utc`, not by another status.
- Inbox is `planned_date IS NULL`, `deleted_at_utc IS NULL`, and pending only.
- Priority is a non-null `low`, `normal`, or `high` value with `normal` default.
- A Task has at most one nullable Category.
- Tags use normalized `tags` and `task_tags` tables.
- Search uses parameterized SQLite `LIKE` over title and description.
- Every SQLAlchemy SQLite connection enables `PRAGMA foreign_keys=ON`.
- AI and ScheduleBlock are not current schema dependencies. V0.5 Deadline,
  Recurrence, and Reminder structures are implemented and present in the
  approved real database at `0005`.

## Frozen V0.3 Decisions

V0.3 contains Calendar, Day View, Week View, Month View, date-only Tasks, and
one optional Time Block per Task. It does not contain Drag & Drop, Resize,
cross-day Time Blocks, Repeat, Calendar Event, Project, Reminder, AI Scheduling,
or external Calendar integration.

### Task Time Model

One Task can have at most one Time Block. The existing `tasks` table will gain:

- `start_at_utc`: nullable UTC instant.
- `end_at_utc`: nullable UTC instant.
- `schedule_timezone`: nullable IANA timezone used to interpret the block.

`planned_date` remains a date-only local calendar value. When a Time Block is
present, it must equal the local date of `start_at_utc` in
`schedule_timezone`. A Time Block therefore requires all four values:
`planned_date`, `start_at_utc`, `end_at_utc`, and `schedule_timezone`.

The state meanings are:

```text
Inbox:       planned_date = NULL, no Time Block
Date-only:   planned_date != NULL, no Time Block
Scheduled:   planned_date != NULL, one complete Time Block
```

The UI should call a date-only Task “未安排时间”, not “全天任务”.

No `all_day`, `schedule_mode`, or `time_block_id` field is planned. A separate
TimeBlock table is not needed while a Task has at most one block.

### Schedule Writes

Task Create/Patch uses one structured `schedule` value so that a block cannot
be partially updated:

```json
{
  "planned_date": "2026-09-26",
  "schedule": {
    "start_time": "14:00",
    "end_time": "15:00",
    "timezone": "Asia/Shanghai"
  }
}
```

`timezone` may be omitted and then defaults to `DAYFLOW_TIMEZONE`.

- Omitted `schedule`: keep the existing Time Block unchanged.
- `schedule: null`: clear the Time Block and keep `planned_date` by default.
- `planned_date: null` together with `schedule: null`: return the Task to Inbox.
- Changing only `planned_date` on a scheduled Task preserves local clock times
  and the stored `schedule_timezone`, then recalculates the UTC instants.

### Conflict Policy

The Backend checks real UTC overlap against active, pending, non-deleted Tasks.
It does not automatically move or reschedule Tasks.

By default, a conflict returns HTTP 409 with error code
`schedule_conflict`. The user may explicitly confirm and retry with the
one-request override `allow_schedule_conflict=true`. The override is not
stored as Task data.

Frontend confirmation copy should be concise Chinese, for example:
“该时间段与已有任务冲突，是否仍然保存？”

Conflict failure and stale-version failure are atomic: no partial update and no
version increment may remain.

## Frozen V0.4 Project Decisions

V0.4 is a single-user Project layer over the existing Task model. Its scope is
Project CRUD, assigning Tasks to one Project, Project detail, dynamic progress,
Project lifecycle actions, and Project-aware Task filtering/display. It does not
introduce a second Task CRUD system or a workflow/kanban model.

### Project Model

The planned `projects` table contains only fields required by V0.4:

- `id`: application-generated UUID stored as text.
- `name`: required trimmed name.
- `description`: nullable text.
- `status`: `active` or `completed`.
- `created_at_utc` and `updated_at_utc`: UTC instants.
- `completed_at_utc`: nullable UTC instant.
- `deleted_at_utc`: nullable UTC instant for soft delete.
- `version`: integer optimistic-concurrency version starting at 1.

Color, icon, deadline, start date, sort order, archive state, pause state,
hierarchy, and persisted progress are deliberately deferred. Project names are
unique only among non-deleted Projects. Trimmed, case-insensitive duplicate
validation is a service/API responsibility backed by a partial unique index;
SQLite `NOCASE` limitations for non-ASCII case folding remain documented.

### Task Relationship and Lifecycle

V0.4 adds nullable `tasks.project_id`. A Task belongs to zero or one Project,
and a Project contains zero or more Tasks. Inbox, planned-date, Calendar,
Priority, Category, Tag, schedule, complete, restore, and soft-delete semantics
remain unchanged. An Inbox Task may belong to a Project, and a Project Task may
have no planned date or Time Block.

Project lifecycle rules are fixed:

- `complete` changes only the Project to `completed` and sets
  `completed_at_utc`; it never completes associated Tasks.
- `reopen` changes only a completed Project to `active` and clears
  `completed_at_utc`.
- `DELETE` soft-deletes the Project and, in the same transaction, clears
  `project_id` on every associated Task, including soft-deleted Tasks.
- Every affected Task version increases at most once for that delete operation.
- `restore` clears only the Project's soft-delete marker and preserves its
  status/completion timestamp. It never reconstructs historical Task
  relationships; a name collision with an active Project returns HTTP 409.
- Task completion never changes Project status.

All Project mutations require the current Project `version` and increment it
once on success. Task assignment, clearing, or Project deletion follows the
existing one-PATCH/one-version-increment rule; an affected Task's
`updated_at_utc` is updated with that single version change. Multi-row changes
use one transaction and roll back completely on validation, conflict, or
database failure.

### Progress and Query Boundaries

Progress is computed dynamically and is never stored. For a non-deleted Project:

```text
completed active Tasks / total active Tasks
```

Soft-deleted Tasks are excluded from both numerator and denominator. Completed
Tasks remain in the denominator. An empty Project reports 0% and zero Tasks.
Project list queries must obtain counts and completed counts with grouped
aggregates (or an equivalent bounded query plan), not one query per Project.

Project detail reuses the existing Task list/filter path with
`project_id=<uuid>`. The Task editor gains a Project selector, and Today,
Inbox, Search, and Calendar may display a compact Project name without changing
their existing date, status, or deletion semantics.

### V0.4 Frontend Boundary

The existing Hash navigation remains in use: `#projects` for the Project list
and `#project:<id>` for Project detail. The minimum frontend units are a
Projects view, a Project detail view, and the existing Task Editor extension.
No Vue Router, Pinia, new UI framework, Kanban board, or project-specific drag
interaction is introduced.

## V0.5 Implementation: Deadlines, Repeat, and Reminders

V0.5 architecture is frozen and implemented in Backend and Frontend. Migration
0005 was verified on temporary copies, backed up, and applied to real data after
explicit approval. Automated, manual visual, and final read-only acceptance passed.

### Feature Boundary

V0.5 contains only:

- Date-only and specific-time Deadlines.
- `daily`, `weekly` with selected weekdays, and `monthly` rules for days 1–28.
- Explicitly specified-time Reminders.

V0.5 does not contain repeated Time Blocks, relative Deadline Reminders,
background reminder services, complex recurrence protocols, external calendar
integration, AI scheduling, or other V0.6+ features.

### Deadline Model

Deadline is independent from `planned_date` and from the optional Time Block.
The proposed Task fields are:

- `deadline_date`: nullable local calendar date.
- `deadline_at_utc`: nullable UTC instant for a specific-time Deadline.
- `deadline_timezone`: nullable persisted IANA timezone used for date-only
  overdue evaluation and for interpreting a timed Deadline.

The valid states are:

```text
No Deadline:    deadline_date = NULL, deadline_at_utc = NULL,
                deadline_timezone = NULL
Date-only:      deadline_date != NULL, deadline_at_utc = NULL,
                deadline_timezone != NULL
Timed:          deadline_date != NULL, deadline_at_utc != NULL,
                deadline_timezone != NULL
```

For a timed Deadline, `deadline_date` must equal the local date of
`deadline_at_utc` in `deadline_timezone`. The Backend uses the saved timezone,
not the browser timezone, to determine overdue state. A date-only Deadline is
overdue when the Backend's local date in that saved timezone is later than the
saved date. A timed Deadline is overdue when the current UTC instant reaches
the saved instant. Completed Tasks retain their Deadline data but are not
reported as currently overdue; deleted Tasks are excluded from normal due and
overdue queries.

Deadline conversion uses `zoneinfo` and rejects invalid, ambiguous, or
nonexistent local times with HTTP 422. Deadline changes do not change
`planned_date`, a Time Block, Project membership, Category, Tags, or Task
status.

### Repeat Model and Lifecycle

V0.5 uses a normalized `recurrence_rules` table and adds a nullable paired
`recurrence_rule_id` plus `recurrence_occurrence_date` to `tasks`. A Task is an
occurrence snapshot; it may belong to at most one rule. Repeated Time Blocks
are not supported, so a recurring Task cannot create a repeated schedule.

Rules store frequency, the weekly weekday mask or monthly day when applicable,
the first local occurrence date, the persisted IANA timezone,
`stopped_at_utc`, timestamps, and an optimistic `version`. Daily rules do not
store a weekday mask; weekly rules require at least one selected weekday;
monthly rules accept only days 1–28.

The pair `recurrence_rule_id` and `recurrence_occurrence_date` is either both
NULL or both non-NULL. Occurrence dates are unique per rule, including rows
that are soft-deleted. `tasks.recurrence_rule_id` uses `ON DELETE RESTRICT` so a
referenced rule cannot be physically deleted; normal stopping uses
`stopped_at_utc`.

The lifecycle is deliberately explicit:

- Normal Task `DELETE` soft-deletes only the current occurrence and does not
  generate another one.
- For an active rule, `Skip` soft-deletes the current occurrence and creates
  its next occurrence in one transaction; a stopped rule creates nothing.
- For an active rule, `Complete` completes the current occurrence and creates
  its next occurrence in one transaction; a stopped rule creates nothing.
- The next date must be later than both the current occurrence date and today
  in the rule timezone. Missed dates are never backfilled.
- `Stop` stops the rule without deleting historical Tasks.
- `Restore` restores only the selected Task; it does not restart the rule or
  restore historical relationships.
- Explicit `Materialize` is the only standalone generation operation. It is
  never called from frontend startup or a GET endpoint, creates at most one
  occurrence, does not backfill, and is idempotent when a pending occurrence
  already exists. A candidate date that conflicts with any historical,
  including soft-deleted, occurrence is skipped.

Editing an occurrence changes that Task snapshot only. Editing a recurrence
rule changes future generation; already generated unfinished Tasks are not
rewritten, deleted, or silently rescheduled. Generated occurrences do not copy
absolute Deadlines, Reminders, or Time Blocks. Valid ordinary metadata such as
title, description, priority, Category, Tags, and Project may be copied under
service validation.

### Reminder Model and Runtime Behavior

Reminders are separate records so a Task can have more than one explicitly
specified trigger. Their persisted state is:

```text
pending → acknowledged
pending → dismissed
```

`due` is derived from `pending` plus `trigger_at_utc <= now_utc` and is never
stored. A due query may exclude completed or soft-deleted Tasks without
mutating their Reminder rows. `GET /api/v1/reminders/due` is strictly
read-only. Only explicit user actions call acknowledge or dismiss endpoints.

When the browser and Backend are running, frontend polling can surface due
Reminders. When the browser is closed but the Backend runs, due records remain
available but no reliable browser popup is promised. When the Backend is
stopped, real-time reminders are unavailable. On reopening, pending due
Reminders can be displayed. `sessionStorage` deduplicates dialogs within one
browser session; it is not a server-side acknowledgement.

### V0.5 Maintenance and Test Boundary

The independent V0.4 footer maintenance fix was completed in `b7b5114`;
`App.vue` reads the application version from the Frontend package metadata.
It is separate from Migration 0005 and V0.5 feature work.

V0.5 implementation and real-data acceptance are complete. The V0.5.1 UI/UX
patch is kept separate from the V0.5 Backend and Migration 0005 work; it does
not change API contracts or database schema. Future visual refinement remains
backlog work and is not automatically part of V0.6.

## Frozen V0.5.1 UI/UX Architecture

### Scope and Non-Goals

V0.5.1 refactors presentation and interaction consistency only. It keeps Vue 3,
TypeScript, Vite, Element Plus, and existing Hash navigation. No new business
feature, dependency, Router, Pinia, UI/state framework, or generic CRUD engine
is introduced. Backend APIs and Task/Project/Deadline/Recurrence/Reminder
semantics remain unchanged. Any improvement requiring Backend support must be
reported for separate approval rather than worked around or added silently.
No migration is created; the real schema remains
`0005_add_deadlines_recurrence_reminders`. Product metadata is `0.5.1` for
this released UI/UX patch; formal release status is determined by Git
tags.

### Design Tokens

Use CSS variables, Element Plus theme variables, and local component classes.
Avoid widespread selectors targeting Element Plus internal DOM. The following
values are the frozen and implemented design baseline:

| Token group | Baseline |
| --- | --- |
| Font family | System sans-serif; Chinese fallbacks PingFang SC and Microsoft YaHei; no downloaded fonts |
| Typography | Page title 28px/1.3; section title 18px/1.4; Task title 15px/1.5; body 14px/1.5; supporting copy 12px/1.5 |
| Spacing | 4, 8, 12, 16, 24, 32, 48px |
| Radius | Input/button 8px; cards and Dialogs 12px; badges 6px |
| Border | 1px solid #E6EBF2; stronger control border #CBD5E1 |
| Background | App #F5F7FB; surface #FFFFFF; subtle surface #F8FAFC |
| Text | Primary #152033; secondary #475467; supporting #667085 |
| Semantic colors | Brand #2F7D73; danger #B42318; warning #B54708; success #28705E; neutral #475467 |
| Focus | Visible 2px brand outline with 2px offset; no removal without an equivalent indicator |
| Control size | Default 36px; primary capture input 40px; compact controls no less than 32px |
| Content width | Task pages max 1040px; Projects max 1280px; Calendar fills available width, max 1680px |
| Sidebar | 220px normally; 192px in compact desktop layout |
| Workspace padding | Horizontal 32px normally, 20px in compact desktop; vertical 32px normally, 24px compact |

Normal Priority and organizational badges are neutral. High Priority and
overdue deadlines get emphasis; warning color is reserved for relevant
attention states such as due today. Completed Tasks remain visible with
restrained styling. Meaning cannot rely on color alone. Validate text contrast,
focus, and disabled-state legibility during implementation and visual review.
Use one primary button per action area, clear labels for inputs/selects,
consistent light-bordered cards, and a shared page-title/state design.

### Responsive and Navigation Rules

Acceptance viewports are 1440×900 and 1024×768. Compact desktop rules begin at
approximately 1200px (the initial breakpoint is max-width: 1199px), not only at
Header actions and filters may wrap; task content must shrink safely.
The Sidebar keeps 今天, 收件箱, 日历, 搜索, 项目 and existing Hash destinations.
Remove decorative 01–05 indices; do not invent counts. Keep the brand and
package-derived version. Active navigation has a visual and accessible state.

Week View may use a clearly bounded internal horizontal scroll area. Header,
date-only rows, and timeline columns stay aligned; horizontal overflow must
not propagate to the whole page. No mobile acceptance claim is made.

### TaskCard Contract

1. Primary: completion state, title, and main edit entry.
2. Secondary: Time Block, Deadline, and Project.
3. Supporting: Category, Tags, Repeat, and other low-frequency metadata.

Keep all existing actions accessible, including complete, restore, delete,
Undo, and skip. A More Menu is allowed, but actions cannot depend on hover.
Long titles/notes and many tags use restrained summaries with accessible full
details. Normal Priority is neutral; High/Overdue are prominent. Do not change
task-list membership, ordering, status, or deadline computation. Display-only
summaries must not introduce per-card Rule/Reminder API queries.

### TaskEditor Contract

Keep one TaskEditor, grouped into 基础信息, 日期与时间, 项目与分类, and 重复与提醒.
The Task save action is labelled 保存任务 and lives in the Dialog Footer.
Use a 700px desktop Dialog (within the approved 680–720px range), constrained
by available width. At 1024×768, the body scrolls internally and the Footer
stays accessible; date/select popovers must remain usable.

Repeat and Reminder use independent management areas and save actions marked
立即生效. Never offer 保存全部: Task, Rule, and Reminder have separate API,
version, and transaction boundaries. Before a Task exists, these areas are
non-editable with the explanation 保存任务后可设置重复和提醒.

Expanding/collapsing a section must preserve drafts, original values, touched
flags, and validation. Invalid sections open and expose their errors. An
independent operation must not silently close the editor and discard a Task
draft; either preserve it or require an explicit discard decision. Cancelling
the editor cannot undo already saved independent operations.

Keep omitted/null semantics: untouched Deadline/Schedule fields stay omitted;
explicit clearing sends null; clearing Tags sends []; Category and Project
clear values normalize undefined to null at the API boundary. Deadline remains
independent of planned_date and Time Block. Preserve stored timezones and
Task/Rule/Reminder versions. Keep time conflict confirmation and stale-version
handling distinct. Grouping is not a reason to change write payload semantics.

### Page and Calendar Contracts

Today uses compact statistics, Quick Capture, and Task List. Inbox puts Quick
Capture first. Search separates its copy and presentation responsibility from
Inbox while preserving existing query/filter semantics. Projects improves card
hierarchy and the Detail Header, not workflow; progress remains Backend-owned.

Calendar shares a compact toolbar and consistent Day/Week/Month design.
Date-only Tasks remain 未安排时间. Empty ranges retain Calendar structure;
loading and error are explicit and never presented as empty success. Short
Time Blocks prioritize title and start/end time, with accessible full details.
Overlapping blocks get display-only side-by-side lanes; do not move Tasks,
forbid overlap, or alter conflict override semantics. Keep true time positions
and duration geometry; do not inflate the scheduled interval to fit labels.
Columns and hour scale align across local scrolling. Completed Tasks remain
visible. Time Block formatting uses each Task's schedule_timezone; Today uses
Backend runtime local_date, not browser timezone. Date-only parsing remains
date-only. No Drag & Drop, Resize, Calendar library, or new range API is added.

### Reminder Contract

Add a global entry only for current due/pending Reminders, using existing
GET /api/v1/reminders/due and existing Task/Reminder actions. This is not a
global future/history Reminder Center. Opening, refreshing, polling, or merely
closing its container cannot acknowledge or dismiss a Reminder.

Keep 45-second polling and sessionStorage deduplication for automatic dialogs.
Deduplication must not hide pending items from the visible due list or alter
Backend state. Queue automatic prompts and prevent concurrent duplicate
prompts. Only explicit 确认提醒 or 关闭提醒 performs the corresponding mutation.
Acknowledgement failure never triggers dismissal. Polling/action failures show
an understandable error and Retry rather than a normal empty list. A failed
mutation preserves pending availability. Closing the global panel is not the
same operation as closing a Reminder. No OS/background notification guarantee
is made while the browser or Backend is stopped.

### Component and Test Boundaries

Permitted minimal extractions: PageHeader, PageState, Repeat management area,
Reminder management area, and Calendar Time Block positioning/display helpers.
App owns Hash navigation; TaskEditor owns Task drafts/payload construction;
Repeat and Reminder areas retain their own independent API actions. Avoid
generic CRUD engines, future-use abstractions, and unrelated service rewrites.

Each Phase 0–5 requires independent review and commit; see ROADMAP.md for
ordering. Relevant tests run at each phase, followed by the complete Phase 5
gate: Backend regression, Frontend Vitest, type-check, build, all 21 existing
Browser E2E scenarios plus focused additions, diff/secret checks, and manual
visual review at both desktop sizes. Existing assertions cannot be deleted
merely to turn tests green; copy/locator changes preserve behavioral checks.
Add editor grouping/draft/payload coverage, overlap and short-block coverage,
responsive overflow/Dialog coverage, and Reminder interaction/failure coverage.
Automated success does not imply manual visual acceptance. All write tests use
isolated temporary 0005 databases through the fail-closed E2E runner; never real
Tasks or Projects. Do not start or replace real services for this design phase.

## Timezone Strategy

- Database stores Time Block instants in UTC.
- `schedule_timezone` stores the IANA timezone used for that block.
- A new block defaults to the configured `DAYFLOW_TIMEZONE`.
- Backend uses Python `zoneinfo` for conversion and validation.
- Ambiguous and nonexistent local times caused by DST return HTTP 422; the
  Backend must not silently select an offset.
- Frontend formats a Time Block using the Task's `schedule_timezone`.
- Date-only `planned_date` values are never parsed as JavaScript UTC dates.
- Backend runtime date/timezone information is exposed through
  `GET /api/v1/runtime`, not through `/healthz`.

## Calendar Boundaries

Calendar uses one range query and the existing Task representation. Day, Week,
and Month views calculate an inclusive local-date range and call the same API.

Today remains a separate compatibility view based on `planned_date`; a
scheduled Task still appears in Today for its local planned date. Completed
Tasks remain visible according to the existing Today behavior, while deleted
Tasks remain hidden.

## Frontend Boundaries

The V0.3 frontend adds `CalendarView` and small Day/Week/Month renderers. It
continues to use Hash navigation, Vue 3, TypeScript, Vite, and Element Plus.
TaskEditor is the single schedule write surface and sends the structured
schedule payload, including explicit `schedule: null` when the user clears a
Time Block. Calendar uses Backend runtime `local_date` and
`schedule_timezone`-aware `Intl.DateTimeFormat` output.

V0.3 does not add Vue Router, Pinia, another global state library, a Calendar
library, or a Drag library. Task Editor remains the write surface for schedule
changes. Calendar refreshes after a successful mutation and has explicit
loading, error, empty, and conflict states.

## Error and Safety Boundaries

- API validation returns the stable `{error: {code, message, details}}` envelope.
- A stale Task `version` returns HTTP 409 and never overwrites newer data.
- A schedule conflict returns HTTP 409 and never partially applies the update.
- Every multi-field Task update commits once or rolls back completely.
- Every SQLAlchemy SQLite connection enables `PRAGMA foreign_keys=ON`, including
  migration and test connections.
- Database exceptions are logged, rolled back, and returned as a meaningful
  generic error; internal tracebacks are not sent to the browser.
- Tests configure dependency overrides backed by temporary SQLite files.
- Browser E2E uses a fail-closed `/tmp/dayflow-e2e-*` database and never falls
  back to `data/dayflow.sqlite3` or `data/backups/`.

## Migration Safety

V0.3 schema work is implemented as `0003_add_task_schedule`, based on
`0002_add_priority_categories_tags`; the real database advanced to `0004` after
the V0.4 migration.
`0001` and `0002` remain immutable.

V0.4 schema work is implemented as `0004_add_projects`, based on `0003`, and
has been tested on clean and real-data temporary copies before approval. It is
now applied to the real database. Existing Tasks retained all legacy values
and received `project_id = NULL`.

Before a real-data migration, the Backend must be stopped, a verified backup
must be created, and the migration must pass on a copy of the current database.
A downgrade must fail closed when any Project or Project relationship would be
lost.

## V0.3 Implementation Boundary

The approved order is:

```text
0003 implementation → temporary-copy migration test → Backend/API → Frontend Calendar
→ Vitest → Browser E2E → real-data migration approval → manual acceptance
```

The V0.4 implementation order was:

```text
0004 temporary migration → Project backend/model/API → backend regression
tests → Phase 1 review → Hash-based Project list/detail → Task Editor
integration → Vitest and Browser E2E → real-data backup and migration approval
→ final acceptance and database verification
```

No V0.4 product implementation may enter a release outside its approved
Project scope. V0.5+ features such as reminders, recurrence, AI, and external
integrations remain out of scope.
