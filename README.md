# IPB Moderation System

This project is a web-based application that monitors user activities and detects unusual or suspicious behavior, providing tools for analysis and management.

## Table of Contents

1. [Features](#features)
2. [Directory Structure](#directory-structure)
3. [Technologies Used](#technologies-used)
4. [Setup Instructions](#setup-instructions)
5. [Usage](#usage)

## Features

- **Dynamic Editable Tables**: Add, edit, and delete rows directly in the browser.
- **Real-Time Database Updates**: Changes are saved automatically to the SQLite database.
- **Logging**: Comprehensive logging for application activity and error tracking.
- **Threaded Monitoring**: Background monitoring for specified forum.
- **Health Check Endpoint**: API health status with uptime details.
- **Custom Styling**: Clean and responsive design with CSS.

## Directory Structure

```
project/
├── static/
│   ├── styles.css         # CSS styles for the frontend
│   └── jquery-3.6.0.min.js # jQuery library
├── js/
│   └── table-management.js # JavaScript for dynamic table functionality
├── templates/
│   └── index.html         # Main HTML template
├── database.py            # Database models and utilities
├── helpers.py             # Logger setup and utilities
├── main.py                # FastAPI application
├── nulled.py              # Forum monitoring logic
└── README.md              # Project documentation
```

## Technologies Used

- **Frontend**:
  - HTML/CSS
  - JavaScript (jQuery)

- **Backend**:
  - FastAPI
  - SQLAlchemy

- **Monitoring**:
  - BeautifulSoup
  - Requests
  - ThreadPoolExecutor

---

## Setup Instructions

### Prerequisites
- Python 3.9 or higher
- `pip` for Python package management
- SQLite (default database)

### Installation

1. Clone the Repository
Open your terminal, clone the repository, and navigate to the project directory:
```bash
git clone https://github.com/dinoz0rg/nulled-moderation-v2.git
cd nulled-moderation-v2
```

2. Install Dependencies
Create a virtual environment, activate it, and install the required dependencies:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
pip install -r requirements.txt
```

3. Set Up Environment Variables
Create a `.env` file in the root directory and add the required configurations:
```env
BASE_URL=<your_base_url>
USER_COOKIE_STR=<your_user_cookie>
MOD_COOKIE_STR=<your_mod_cookie>
```

4. Start the Server
Run the server script:
```bash
python3 main.py
```

5. Start the Monitoring Process
```bash
curl -X POST "http://localhost:8000/start-monitor?max_threads=5&page_range=3&cycle_delay=120"
```

6. Access the Application
Open your web browser and navigate to:
[http://localhost:8000](http://localhost:8000)


## Usage

### Editable Tables
- Navigate to the Descriptions, Titles, or Links sections.
- Click on any table cell to edit or add new entries.
- Changes are saved automatically when you click outside the cell.

### Health Check
- API endpoint: `/health`
- Provides application status and uptime in seconds.

### Background Monitoring
- Start monitoring via the API endpoint `/start-monitor`.
- Stop monitoring via the API endpoint `/stop-monitor`.


## API Documentation


### Docs
```bash
http://localhost:8000/docs
```

### Redoc
```bash
http://localhost:8000/redoc
```
