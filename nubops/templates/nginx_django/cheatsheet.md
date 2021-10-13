target: {project_dir}/cheatsheet.md

# Cheatsheet for ${project}

To to interactively monitor the nginx log files:

```bash
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

When a connection is made to socket, systemd will automatically start the
`${project}.service` to handle it:

```bash
sudo systemctl start ${project}.socket
sudo systemctl enable ${project}.socket
```

To check if everything is ok use the following commands:

```bash
sudo systemctl status ${project}.socket
sudo systemctl status ${project}
```

If you got any problem, use the following commands to check logs:

```bash
sudo journalctl -u ${project}
```

After changing the socket or service file it is necessary to reload the daemon
and gunicorn by running:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ${project}
```

To check nginx settings:
```bash
nginx -t
```
