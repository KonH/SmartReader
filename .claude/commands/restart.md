Stop and start the SmartReader systemd service:

```bash
systemctl stop smartreader && systemctl start smartreader
```

Report the result. If either command fails, show the error and run `systemctl status smartreader --no-pager --lines=20` to help diagnose the issue.
