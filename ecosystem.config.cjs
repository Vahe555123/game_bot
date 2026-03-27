module.exports = {
  apps: [
    {
      name: "game_bot2",
      cwd: "/home/deploy/apps/game_bot2",
      script: "./start_pm2.sh",
      interpreter: "/bin/bash",
      autorestart: true,
      watch: false,
      env: {
        PYTHONIOENCODING: "utf-8",
      },
    },
  ],
};
