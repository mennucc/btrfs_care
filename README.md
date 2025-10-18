# Btrfs Maintenance Script

A Python script for automated maintenance of Btrfs filesystems. Performs scrub and incremental balance operations on all mounted Btrfs partitions.

## Features

- 🔍 **Automatic filesystem discovery**: Finds all mounted Btrfs partitions using `findmnt`
- 🔄 **Smart scrub management**:
  - Skips scrub if one was performed recently (configurable threshold)
  - Detects and resumes interrupted scrubs
  - Skips filesystems with running scrubs
  - Detects and reports errors
- ⚖️ **Incremental balance**: Performs gradual balance operations (0-90% usage levels for both data and metadata)
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

To test the script without making changes, edit the configuration at the top of the file:

```python
# Change this line:
NOACT = []

# To this:
NOACT = ['echo']
```

This will print commands instead of executing them.

### Configuration

Edit these variables at the top of the script:

```python
# Skip scrub if last one was less than this many days ago
SCRUB_MAX_AGE_DAYS = 50

# Dry-run mode (uncomment to enable)
# NOACT = ['echo']
```

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

If scrub completes successfully without errors, the script performs incremental balance:

- **Data balance**: Processes chunks with usage from 0% to 90% in 10% increments
- **Metadata balance**: Same approach for metadata chunks
- **Incremental approach**: Reduces impact on system performance, avoids "out of disk space" errors.

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
============================================================

Found 3 unique Btrfs partitions:
  - / (/dev/nvme0n1p6[/@rootfs]) UUID: a1b2c3d4-e5f6-...
  - /media/root_nvme (/dev/nvme0n1p3) UUID: f1e2d3c4-b5a6-...
  - /data (/dev/sdc2) UUID: 4e252947-b70f-...

============================================================
Starting scrub on: /
Device: /dev/nvme0n1p6[/@rootfs]
UUID: a1b2c3d4-e5f6-...
============================================================
ℹ️  Last scrub: 2025-09-15 10:30:45 (33 days ago)
✓ Scrub is recent (< 50 days), skipping...

============================================================
Starting balance on: /
============================================================

→ Running balance with -dusage=0...
Done, had to relocate 0 out of 45 chunks
→ Running balance with -dusage=10...
Done, had to relocate 3 out of 45 chunks
...
✓ All balance operations completed for /
```

## Scheduling with Cron/Systemd

### Cron

Add to root's crontab (`sudo crontab -e`):

```bash
# Run monthly on the 1st at 3:00 AM
0 3 1 * * /usr/local/bin/btrfs_care >> /var/log/btrfs_maintenance.log 2>&1
```

### Systemd Timer

Create `/etc/systemd/system/btrfs-maintenance.service`:

```ini
[Unit]
Description=Btrfs Maintenance (Scrub and Balance)
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/btrfs_care
StandardOutput=journal
StandardError=journal
```

Create `/etc/systemd/system/btrfs-maintenance.timer`:

```ini
[Unit]
Description=Monthly Btrfs Maintenance

[Timer]
OnCalendar=monthly
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable btrfs-maintenance.timer
sudo systemctl start btrfs-maintenance.timer
```

## Best Practices

1. **Regular execution**: Run monthly or bi-monthly for optimal filesystem health
2. **Monitor logs**: Check output for errors or warnings
3. **Free space**: Ensure at least 10-20% free space before running balance
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
You may need to free up space or use `-dusage=5` for the first balance.

### Script exits during shutdown
This is intentional behavior to prevent data corruption. The script will resume on next execution.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License - feel free to use and modify as needed.

## Links

- Btrfs Wiki: https://btrfs.wiki.kernel.org/
- Script development: https://claude.ai/share/82c11573-908c-4b94-95af-700ff4a6d158

## Credits

Copyright (c) 2025 A C G Mennucci

Developed collaboratively with Claude AI (Anthropic).
