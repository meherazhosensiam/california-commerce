# API documentation

Base URL: `/api`

## Public
- `GET /products`
- `GET /products/{id}`
- `GET /health`

## Authentication
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/reset/request`
- `POST /auth/reset/complete`
- `POST /auth/mfa/verify`
- `GET /me`

## Customer workflows
- `GET /users/{id}`
- `GET /orders`
- `GET /orders/{id}`
- `POST /orders`
- `POST /orders/{id}/cancel`
- `GET /invoices`
- `GET /payments`
- `POST /reviews`
- `GET /support`
- `POST /support`
- `POST /files`
- `GET /files/{id}`

## Employee/admin workflows
- `GET /admin/users`
- `PATCH /admin/users/{id}/role`
- `GET /admin/orders`
- `POST /admin/refunds/{order_id}`
- `GET /admin/audit`
- `GET /admin/files`
- `POST /admin/diagnostics`

## Lab management
- `GET /lab/objectives`
- `POST /lab/submit`
- `GET /lab/score`
- `POST /admin/lab/reset/{user_id}`

The intentionally unsafe behavior is documented only in the author mapping, not the normal UI.
