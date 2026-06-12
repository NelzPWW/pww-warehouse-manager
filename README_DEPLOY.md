# PWW Warehouse Manager DB v1

## Render settings

Build Command:
`pip install -r requirements.txt`

Start Command:
`gunicorn app:app`

## Environment variables

Required:
- `PYTHON_VERSION=3.11.9`
- `SECRET_KEY=<long random secret>`
- `DATABASE_URL=<Render Internal Database URL>`

Optional:
- `PWW_ADMIN_PASS=<Ryan admin password>`
- `PWW_ARNEL_PASS=<Arnel admin password>`
- `PWW_RYAN_PASS=<Ryan admin password>`
- `PWW_STAFF_PASS=<Staff password>`

## Notes

- Product inventory imports now write to PostgreSQL.
- Products survive Render redeploys/restarts.
- Admin Tools can still manually import CSV files.
- Next phase: local shop app sends daily updates to this database/API.
