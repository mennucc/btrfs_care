# Btrfs Maintenance Script

A Python script for automated maintenance of Btrfs filesystems. Performs scrub and incremental balance operations on all mounted Btrfs partitions.

## Features

- 🔍 **Automatic filesystem discovery**: Finds all mounted Btrfs partitions using `findmnt`
- 🔄 **Smart scrub management**:
  - Skips scrub if one was performed recently (configurable threshold)
  - Detects and resumes interrupted scrubs
  - Skips filesystems with running scrubs
  - Detects and reports errors
- ⚖️ **Incremental balance modes**: Default auto mode runs only when free space falls below a tunable threshold, plus `--balance soft/full/no` toggles for different usage sweeps
- 🚫 **Duplicate detection**: Uses filesystem UUID to avoid processing the same filesystem twice (e.g., when mounted in multiple locations)
- 🛑 **Shutdown detection**: Gracefully exits if system shutdown is in progress
- 🧪 **Dry-run mode**: Test the script without making actual changes

## Requirements

- Python 3.6+
- Btrfs filesystem utilities (`btrfs-progs`)
- Root/sudo privileges
- systemd (for shutdown detection)

## Installation

1. Download the script:
```bash
wget https://raw.githubusercontent.com/mennucc/btrfs_care/refs/heads/main/btrfs_care
chmod +x btrfs_care
```

2. Or clone the repository:
```bash
git clone https://github.com/mennucc/btrfs_care.git
cd btrfs_care
chmod +x btrfs_care
```

Then you can create a Debian/Ubuntu package with `dpkg-buildpackage.sh -us -uc`

## Usage

### Basic Usage

Run with root privileges:

```bash
sudo ./btrfs_care
```

Or with Python:

```bash
sudo python3 btrfs_care
```

### Dry-Run Mode

To simulate the workflow without touching disks, run with `--no-act`:

```bash
sudo ./btrfs_care --no-act
# or
sudo python3 btrfs_care --no-act
```

This echoes every `btrfs` command that would have run.

### Test Mode (no sudo)

To exercise the code paths without touching disks, use the bundled fixtures under `fakebin/`:

```bash
python3 btrfs_care --test-debug
```

This forces `--no-act`, injects `fakebin/` at the front of `PATH`, bypasses the root check, and logs against the captured `findmnt`, `btrfs`, and `journalctl` transcripts.

### Customize Scrub Frequency

Override the “skip scrub if already run recently” threshold per execution:

```bash
sudo ./btrfs_care --scrub-max-age-days 30
```

That example reruns scrubs whenever the previous pass is 30+ days old (default is 50 days).

### Customize Balance Strategy

Balance runs can be tuned per invocation with `--balance {auto,soft,full,no}` and the optional `--auto-balance-threshold PCT`:

- `auto` (default): Inspect metadata/data free space and run balance only when either drops below the threshold (default 15%), using usage passes `0/5/10/15`. Adjust the trigger with `--auto-balance-threshold 12.5`.
- `soft`: Always run incremental passes at `0/5/10/20/30` usage for both data and metadata—lighter than a full sweep but still proactive.
- `full`: Keep the original 0-90% passes in 10% steps (plus the 5% pass) for the most aggressive rebalancing.
- `no`: Skip balance entirely (scrubs still run according to `--scrub-max-age-days`).

`--auto-balance-threshold` only has an effect when `--balance=auto`; other modes always follow their fixed pass sets.

Pair this flag with `--no-act` or `--test-debug` when you want to validate the control flow without touching live disks.

### Configuration

Edit these defaults near the top of the script if you want different baseline behavior:

```python
# Skip scrub if last one was less than this many days ago
SCRUB_MAX_AGE_DAYS = 50

# Dry-run mode is now controlled via --no-act / --noact CLI flag
# Default threshold for --balance=auto (percentage of free space)
AUTO_BALANCE_THRESHOLD_DEFAULT = 15.0
```

`SCRUB_MAX_AGE_DAYS` only defines the default for the CLI; you can override it dynamically with `--scrub-max-age-days DAYS` as shown above.

### Capture Kernel Error Context

Every run scans recent kernel logs for Btrfs warnings/errors on each device, maps the reported `root` IDs back to their subvolume paths, and prints the affected files. While a scrub/balance is in progress, the script also tails `journalctl -k` so new warnings show up immediately. To persist those findings, pass `--log /path/to/log`; add `--log-format json` if you prefer structured entries instead of the default text summary, and optionally `--log-rotate 10MiB` (accepts size suffixes like k/MB/MiB) to keep the log bounded with up to four backups.

### Tests

A growing test suite covers both the parser helpers and an end-to-end CLI run against the `fakebin/` fixtures. Run everything with:

```bash
python3 -m unittest tests.test_journal tests.test_cli
```

The CLI tests invoke `python3 btrfs_care --test-debug` under the hood, so they don’t need sudo or live disks. Add more cases alongside these whenever you touch logging, argument parsing, or fixture behavior.

### Debian/Ubuntu Packaging

The repository includes a ready-to-build `debian/` directory. To produce a `.deb`:

```bash
./dpkg-buildpackage.sh
```

The helper script archives `git HEAD` into a temporary directory, runs `dpkg-buildpackage` with provided arguments, and copies the resulting `.deb/.dsc/.changes/.buildinfo` artifacts into `build/`.

The installed package drops `btrfs_care` under `/usr/bin`, places the systemd service/timer units in `/lib/systemd/system/`, the fixtures under `/usr/lib/btrfs_care/fakebin/`, and the man page as `btrfs_care(1)`.

## How It Works

### 1. Filesystem Discovery

The script uses `findmnt --json -t btrfs` to discover all mounted Btrfs filesystems and their mount points. It then:
- Recursively processes all mount points (including subvolumes)
- Retrieves the UUID of each filesystem
- Filters duplicates to process each unique filesystem only once

### 2. Scrub Operation

For each filesystem, the script:

1. **Checks scrub status**:
   - If a scrub is running → skips this filesystem
   - If a scrub was interrupted → resumes it
   - If last scrub was recent → skips scrub
   - Otherwise → starts a new scrub

2. **Runs in foreground** (`-B` flag): The script waits for scrub completion before proceeding

3. **Reports errors**: Checks for data corruption or read errors

### 3. Balance Operation

If scrub completes successfully without errors, the script consults `--balance` to decide how aggressively to run incremental balance:

- **`auto` (default)**: Checks metadata/data free space from `btrfs filesystem usage` and only runs when either side drops below the configured threshold (default 15%), issuing `0/5/10/15` passes.
- **`soft`**: Always performs the lighter `0/5/10/20/30` passes for both data and metadata.
- **`full`**: Matches the legacy behavior with passes at `0, 5, 10, 20, ..., 90`.
- **`no`**: Skips balance entirely; useful when you only want monitoring and scrubs.

Each run still balances data chunks first, then metadata chunks, to limit IO bursts and avoid out-of-space failures.

### 4. Shutdown Detection

Before processing each filesystem, the script checks if system shutdown is in progress using multiple methods:
- systemd shutdown target status
- systemd system state
- Presence of shutdown schedule file
- System runlevel

If shutdown is detected, the script exits gracefully.

## Output Example

```
Btrfs Maintenance Script
============================================================
Configuration: Skip scrub if last run was < 50 days ago
Balance mode: auto
Auto balance threshold: 15.00% free
Mode: Live execution
============================================================

Found 2 unique Btrfs partitions:
  - / (/dev/nvme0n1p5[/@ubuntu2204]) UUID: 5555f991-db31-45a1-b146-7e0f386aa59e
  - /media/allext (/dev/sdh1[/mirrors]) UUID: 373b883a-fb68-4af4-9c3a-47e827c5899b

============================================================
Working on: /
Device: /dev/nvme0n1p5[/@ubuntu2204]
UUID: 5555f991-db31-45a1-b146-7e0f386aa59e
   ⓘ Metadata profile=DUP size=9.95 GiB used=7.69 GiB free=2.26 GiB (22.68% free)
   ⓘ Data profile=SINGLE size=431.61 GiB used=424.57 GiB free=7.03 GiB (1.63% free)
   ⚠️  Kernel reported 1 Btrfs event(s) on nvme0n1p5:
      - [2025-11-07T14:11:11+01:00 theserver2] WARNING root ?, inode ?, path - — space cache v1 is being deprecated and will be removed in a future release, please use -o space_cache=v2

============================================================
Starting scrub on: /
Device: /dev/nvme0n1p5[/@ubuntu2204]
UUID: 5555f991-db31-45a1-b146-7e0f386aa59e
============================================================
ℹ️  Last scrub: 2025-10-18 11:40:32 (21 days ago)
✓ Scrub is recent (< 50 days), skipping...
   ℹ️  Auto balance triggered (threshold 15.00%): data free 1.63%

============================================================
Starting balance on: /
============================================================

→ Running balance with -dusage=0...
Done, had to relocate 0 out of 45 chunks
→ Running balance with -dusage=10...
Done, had to relocate 3 out of 45 chunks
...
→ Running balance with -musage=90...
Done, had to relocate 0 out of 12 chunks

✓ All balance operations completed for /

============================================================
Working on: /media/allext
Device: /dev/sdh1[/mirrors]
UUID: 373b883a-fb68-4af4-9c3a-47e827c5899b
   ⓘ Metadata profile=DUP size=29.00 GiB used=28.12 GiB free=897.39 MiB (3.02% free)
   ⓘ Data profile=SINGLE size=3.63 TiB used=2.82 TiB free=845.59 GiB (19.75% free)
   ⚠️  Kernel reported 0 Btrfs event(s) on sdh1:

============================================================
Starting scrub on: /media/allext
Device: /dev/sdh1
UUID: 373b883a-fb68-4af4-9c3a-47e827c5899b
============================================================
⚠️  Previous scrub was aborted. Resuming...
...
```

## Scheduling with Cron/Systemd

### Cron

Add to root's crontab (`sudo crontab -e`):

```bash
# Run monthly on the 1st at 3:00 AM
0 3 1 * * /usr/local/bin/btrfs_care >> /var/log/btrfs_maintenance.log 2>&1
```

### Systemd Timer

Copy the service/timer definitions from `systemd/btrfs_care.service` and `systemd/btrfs_care.timer` into `/etc/systemd/system/`. The service runs `btrfs_care --log /var/log/btrfs_care.log --log-format json --log-rotate 10MiB`; adjust thresholds or rotation strategy as needed.

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable btrfs_care.timer
sudo systemctl start btrfs_care.timer
```

## Best Practices

1. **Regular execution**: Run monthly or bi-monthly for optimal filesystem health
2. **Monitor logs**: Check output for errors or warnings
3. **Free space**: Aim for 10‑20 % free before maintenance; auto mode only kicks in below its threshold (default 15%, adjustable via `--auto-balance-threshold`), but the initial `-dusage=0` / `-musage=0` passes (auto/soft/full) still need a few GiB of slack
4. **Test first**: Use dry-run mode on new systems
5. **Backup important data**: Always maintain backups before maintenance operations

## Troubleshooting

### "This script requires root privileges"
Run with `sudo` or as root user.

### Scrub reports errors
Investigate immediately:
```bash
sudo btrfs scrub status /mountpoint
sudo btrfs device stats /mountpoint
```

### Balance fails
Check free space:
```bash
sudo btrfs filesystem usage /mountpoint
```
If it still fails, free some space and rerun the script—each balance mode starts with `-dusage=0` / `-musage=0` passes to target low-usage chunks automatically.

### Script exits during shutdown
This is intentional behavior to prevent data corruption. The script will resume on next execution.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.


If you wish to help in developing, please

    git config --local core.hooksPath .githooks/

so that each commit is pre tested.


## License

MIT License - feel free to use and modify as needed.

## Links

- Btrfs Wiki: https://btrfs.wiki.kernel.org/

## Credits

Copyright (c) 2025 A C G Mennucci

Developed collaboratively with Claude AI (Anthropic) and Codex (OpenAI).
