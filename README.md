# SUA project — Radiopostaje

Group: *RADIOlogNIKI*

## Services and documentation

The current Docker Compose setup starts the users service API and its MongoDB database. The Swagger UI is accessible at <http://localhost:9001/docs> .

- **Users API (correct, live FastAPI documentation):** <http://localhost:9001/docs>

## Setup

### Prerequisites

- Docker with the Docker Compose plugin
- A free host port `8081` for Swagger UI, `9001` for the users API, and `7001` for MongoDB (or adjust the corresponding values in `.env`)
- Services should take ports from `9000` upwards, and databases from `7000` upwards.

### Start the project

1. Create your local environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Open `.env` and replace `JWT_SECRET_KEY` with a long, private value. Keep `.env` local; it is ignored by Git. The example file contains a development-only value. The default database URL is configured for the MongoDB container and normally does not need to change.

3. Create the Docker network expected by Compose (only needed once):

   ```sh
   docker network create sua-services-network
   ```

   If Docker reports that the network already exists, continue to the next step.

4. Build and start the services from the project root:

   ```sh
   docker compose up --build
   ```

   To run them in the background, add `-d`: `docker compose up --build -d`.

5. Open the documentation:

   - Users FastAPI docs: <http://localhost:9001/docs>
   - API specification overview: <http://localhost:8081>

MongoDB is published on `localhost:7001`; the users API connects to it through the Compose network. The named `mongo_data` volume keeps database contents between container restarts.

### Stop the project

```sh
docker compose down
```

This stops and removes the containers while preserving the MongoDB volume. To also delete the stored database, run `docker compose down --volumes`.

### Configuration

The `.env.example` file lists the available settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SWAGGER_PORT` | `8081` | Host port for Swagger UI |
| `USERS_API_PORT` | `9001` | Host port for the users FastAPI service |
| `USERS_DATABASE_PORT` | `7001` | Host port for MongoDB |
| `USERS_DATABASE_URL` | `mongodb://users-db:27017/users_db` | MongoDB URL used by the users service inside Docker |
| `JWT_SECRET_KEY` | Set in `.env.example` for development | Secret used to sign users-service JWTs; replace it in `.env` |
| `HASH_ALG` | `HS256` | JWT signing algorithm |
