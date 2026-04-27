# Welcome to My Api
***

## Task
The task is to build a backend API with authentication, token-based authorization, CRUD operations, pagination, caching, documentation, and cloud hosting.  
The main challenge was creating a simple but complete API project that matches the bootcamp requirements while keeping it easy to test and update later with custom data.

## Description
This project is a JavaScript and Express backend API about pipeline transport and its environmental impact.  
It includes JWT authentication for admin actions, public `GET` routes, protected `POST`, `PUT`, and `DELETE` routes, pagination with a maximum of 20 items per page, and Redis support with memory fallback when Redis is not available.  
The API currently uses mock data with more than 1000 records and can later be replaced with custom JSON, CSV, or database-backed data.

## Installation
Clone or download the project, then install dependencies:

```bash
npm install
```

Create a `.env` file from `.env.example` if needed, then run:

```bash
node server.js
```

For development, you can also use:

```bash
npm run dev
```

## Usage
When the server starts, it runs on:

```bash
http://localhost:3000
```

Main routes:

```bash
GET /health
GET /api/pipeline-records?page=1&limit=20
GET /api/pipeline-records/:id
POST /api/auth/register
POST /api/auth/login
POST /api/pipeline-records
PUT /api/pipeline-records/:id
DELETE /api/pipeline-records/:id
```

To use protected routes, first register and login, then send the JWT token in the `Authorization` header:

```bash
Authorization: Bearer YOUR_TOKEN
```

API documentation:

```bash
http://13.49.225.148/api-docs/
```

Example:

```bash
node server.js
```

### The Core Team
2006i
