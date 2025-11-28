#!/bin/bash
set -e

# 等待数据库启动
echo "Waiting for database to be ready..."
while ! nc -z $DATABASE_HOST $DATABASE_PORT; do
  sleep 0.1
done
echo "Database is ready!"

# 运行数据库迁移
echo "Running database migrations..."
python manage.py migrate --noinput

# 创建超级用户（如果需要）
if [ "$DJANGO_SUPERUSER_USERNAME" ] && [ "$DJANGO_SUPERUSER_EMAIL" ] && [ "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Creating superuser..."
    python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
EOF
fi

# 收集静态文件
echo "Collecting static files..."
python manage.py collectstatic --noinput

# 启动应用
echo "Starting application..."
exec "$@"