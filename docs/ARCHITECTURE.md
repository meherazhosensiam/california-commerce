# Architecture

Browser → Nginx → React static frontend / FastAPI API → PostgreSQL + Redis. A separate worker demonstrates asynchronous infrastructure and maintains a Redis heartbeat.

The API intentionally mixes secure and insecure patterns so testers must map behavior rather than navigate a vulnerability menu. The frontend does not contain flags or solution text.

Database entities include users, roles, user_roles, sessions, products, categories, orders, order_items, addresses, invoices, payments, reviews, support_tickets, ticket_messages, uploaded_files, employees, audit_logs, api_keys, notifications, coupons, lab_flags, lab_submissions, and inventory_reservations.
