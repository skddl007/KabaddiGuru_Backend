# KabaddiGuru Backend

Enhanced Kabaddi Analytics API Server with support for both local development and cloud deployment.

## 🚀 Quick Start

### Local Development

1. **Run the setup script:**
   ```bash
   python setup_local.py
   ```

2. **Update configuration:**
   Edit `config.env` with your actual credentials:
   ```env
   DB_PASSWORD=your_actual_password
   GOOGLE_API_KEY=your_google_api_key
   JWT_SECRET=your_secret_key
   ```

3. **Start the server:**
   ```bash
   uvicorn main:app --reload
   ```

4. **Access the API:**
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

### Cloud Deployment

1. **Update deployment configuration:**
   Edit `run-env.yaml` with your Cloud SQL credentials:
   ```yaml
   GOOGLE_API_KEY: "your_google_api_key"
   JWT_SECRET_KEY: "your_jwt_secret"
   DB_USER: "your_db_user"
   DB_PASSWORD: "your_db_password"
   DB_NAME: "your_db_name"
   ```

2. **Deploy to Cloud Run:**
   ```bash
   gcloud run deploy kabaddiguru-backend --source .
   ```

## 📁 Configuration Files

### Local Development (`config.env`)
- **Purpose:** Local development environment
- **Database:** Local PostgreSQL connection
- **Usage:** Loaded automatically when `K_SERVICE` environment variable is not set

### Deployment (`run-env.yaml`)
- **Purpose:** Cloud Run deployment environment
- **Database:** Cloud SQL connection via Unix socket
- **Usage:** Loaded automatically when `K_SERVICE` environment variable is set

## 🔧 Environment Variables

| Variable | Local Default | Description |
|----------|---------------|-------------|
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `5432` | Database port |
| `DB_NAME` | `kabaddi_data` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | `password` | Database password |
| `JWT_SECRET` | `your-secret-key` | JWT signing secret |
| `GOOGLE_API_KEY` | `your-api-key` | Google AI API key |
| `DEBUG` | `true` | Debug mode |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | Frontend URL |

## 🗄️ Database Setup

### Local PostgreSQL

1. **Install PostgreSQL:**
   - Windows: Download from https://www.postgresql.org/download/windows/
   - macOS: `brew install postgresql`
   - Linux: `sudo apt-get install postgresql`

2. **Create database:**
   ```sql
   CREATE DATABASE kabaddi_data;
   ```

3. **Update config.env:**
   ```env
   DB_USER=your_username
   DB_PASSWORD=your_password
   ```

### Cloud SQL (Deployment)

1. **Create Cloud SQL instance**
2. **Update run-env.yaml:**
   ```yaml
   DB_HOST: "/cloudsql/YOUR_PROJECT:YOUR_REGION:YOUR_INSTANCE"
   DB_USER: "your_db_user"
   DB_PASSWORD: "your_db_password"
   DB_NAME: "your_db_name"
   ```

## 🔄 Environment Detection

The application automatically detects the environment:

- **Local Development:** Uses `config.env` and local PostgreSQL
- **Cloud Run:** Uses `run-env.yaml` and Cloud SQL

Detection is based on:
- `K_SERVICE` environment variable (Cloud Run)
- `PORT` environment variable (Cloud Run)

## 📦 Dependencies

### Required Packages
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `psycopg2-binary` - PostgreSQL adapter
- `python-dotenv` - Environment variable loading
- `pandas` - Data manipulation
- `sqlalchemy` - Database ORM
- `langchain` - AI/LLM integration
- `google-generativeai` - Google AI API

### Installation
```bash
pip install -r requirements.txt
```

## 🚀 API Endpoints

### Core Endpoints
- `GET /health` - Health check
- `POST /chat` - Main chat endpoint
- `POST /chat/stream` - Streaming chat
- `GET /suggestions` - Question suggestions
- `GET /stats` - Performance statistics

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/verify` - Token verification

## 🔍 Troubleshooting

### Common Issues

1. **Database Connection Error:**
   ```
   psycopg2.OperationalError: connection to server failed
   ```
   - Ensure PostgreSQL is running
   - Check credentials in `config.env`
   - Verify database exists

2. **Environment Variables Not Loading:**
   - Check file permissions
   - Ensure `config.env` exists in project root
   - Verify file format (no spaces around `=`)

3. **Cloud SQL Connection Issues:**
   - Verify Cloud SQL instance is running
   - Check service account permissions
   - Ensure correct connection string format

### Debug Mode

Enable debug mode in `config.env`:
```env
DEBUG=true
```

This will:
- Show detailed error messages
- Enable CORS for all origins
- Log SQL queries

## 📝 Development

### Project Structure
```
KabaddiGuru_Backend/
├── main.py                 # Main application entry point
├── config.env              # Local development config
├── run-env.yaml           # Deployment config
├── setup_local.py         # Local setup script
├── requirements.txt       # Python dependencies
├── modules/               # Core modules
│   ├── postgresql_loader.py
│   ├── query_cleaner.py
│   └── ...
├── User_sign/             # Authentication module
│   ├── auth_routes.py
│   └── database.py
└── Analytics_Tool/        # Analytics module
    └── analytics_routes.py
```

### Adding New Features

1. **Create module in `modules/` directory**
2. **Add routes to `main.py`**
3. **Update configuration if needed**
4. **Test locally and in deployment**

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally and in deployment
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.
