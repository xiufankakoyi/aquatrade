// PM2 配置文件 - 备选方案（功能更强大）
// 
// 安装: npm install -g pm2
// 启动: pm2 start ecosystem.config.js
// 监控: pm2 monit
// 日志: pm2 logs
// 停止: pm2 stop all
// 重启: pm2 restart all

module.exports = {
    apps: [
        {
            name: 'aquatrade-web',
            script: 'granian',
            args: '--interface asgi server.asgi_entry:asgi_app --host 0.0.0.0 --port 5000',
            interpreter: 'none', // granian 是可执行文件
            cwd: './',
            env: {
                DB_BACKEND: 'lancedb',
                GRANIAN_LOG_LEVEL: 'info'
            },
            autorestart: true,
            watch: false,
            max_memory_restart: '1G',
            error_file: './logs/pm2-web-error.log',
            out_file: './logs/pm2-web-out.log',
            log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
        },
        {
            name: 'aquatrade-worker',
            script: './server/worker.py',
            interpreter: 'python',
            cwd: './',
            env: {
                DB_BACKEND: 'lancedb'
            },
            autorestart: true,
            watch: false,
            max_memory_restart: '500M',
            error_file: './logs/pm2-worker-error.log',
            out_file: './logs/pm2-worker-out.log',
            log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
        },
        {
            name: 'aquatrade-frontend',
            script: 'npm',
            args: 'run dev',
            cwd: './myapp',
            autorestart: true,
            watch: false,
            error_file: './logs/pm2-frontend-error.log',
            out_file: './logs/pm2-frontend-out.log',
            log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
        }
    ]
};
