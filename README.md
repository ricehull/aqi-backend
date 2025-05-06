English---------------------------------------------------------------

## 🛠️ Project Setup and Running Instructions

### 1️⃣ Install Dependencies

Install the required Python packages using `requirements.txt`:

```bash
pip install -r requirements.txt
```

> If you're using a Python virtual environment (recommended), activate it first:
>
> ```bash
> source .venv/bin/activate
> ```

---

### 2️⃣ Initialize the Database (MySQL)

1. Install and start the MySQL server.
2. Import the provided database backup using the MySQL client:

```bash
mysql -u your_user -p your_database < scripts/mydatabase_backup.sql
```

Or log into the MySQL client and run:

```sql
source scripts/mydatabase_backup.sql;
```

---

### 3️⃣ Start the Backend (Django)

This project uses Django’s built-in development server for demonstration purposes.

#### 💡 Optionally, kill any existing Django server process to avoid port conflicts:

```bash
pkill -f "python manage.py runserver"
```

#### ✅ Start the server:

```bash
# If using a virtual environment, activate it first:
source .venv/bin/activate

# Start Django backend:
python manage.py runserver 0.0.0.0:8000
```

> The server will listen on all network interfaces, port 8000 by default.




中文---------------------------------------------------------------

## 🛠️ 项目配置与运行说明

### 1️⃣ 安装依赖

请在项目根目录下运行以下命令，安装 Python 依赖：

```bash
pip install -r requirements.txt
```

> 如果你使用的是虚拟环境（推荐），请先激活虚拟环境：
>
> ```bash
> source .venv/bin/activate
> ```

---

### 2️⃣ 初始化数据库（MySQL）

1. 安装并启动 MySQL 服务。
2. 使用 MySQL 客户端导入数据库备份文件：

```bash
mysql -u your_user -p your_database < scripts/mydatabase_backup.sql
```

或在 MySQL 客户端中执行：

```sql
source scripts/mydatabase_backup.sql;
```

---

### 3️⃣ 启动后端服务（Django）

该项目使用 Django 自带的开发服务器用于演示。

#### 💡 启动前确保端口未被占用（可选）：

```bash
pkill -f "python manage.py runserver"
```

#### ✅ 启动服务：

```bash
# 如果使用虚拟环境，请先激活：
source .venv/bin/activate

# 启动 Django 后端服务：
python manage.py runserver 0.0.0.0:8000
```

> 默认监听在所有 IP 上的 8000 端口。

