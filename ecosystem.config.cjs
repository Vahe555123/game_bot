module.exports = {
  apps: [
    {
      name: "game_bot2",
      cwd: "/home/deploy/apps/game_bot2",
      script: "./start_pm2.sh",
      interpreter: "/bin/bash",
      autorestart: true,
      watch: false,
      max_restarts: 10,
      restart_delay: 3000,
      env: {
        PYTHONIOENCODING: "utf-8",
        NODE_ENV: "production",
        APP_ENV_FILE: "/home/deploy/apps/game_bot2/.env",
        // deploy.yml может выставить через export перед pm2; иначе .env на сервере (см. .env.example)
        SQLITE_SKIP_FTS_REBUILD_ON_STARTUP:
          process.env.SQLITE_SKIP_FTS_REBUILD_ON_STARTUP || "false",
      },
    },
  ],
};
