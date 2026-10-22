/** Synthetic, ready-to-run MWS examples. No personal or production data. */
export const ADDITIONAL_WORKLOAD_PRESETS = [
  {
    id: "students",
    eyebrow: "COLLEGE DATABASE",
    title: "Student records",
    copy: "Find a student by roll number, filter by department, and browse students by year.",
    spec: `version: mws-0.1
name: college_students
record_count: 120000
fields:
  - name: roll_id
    type: uint64
    cardinality: 120000
  - name: department
    type: string
    cardinality: 20
  - name: year
    type: uint32
    cardinality: 5
queries:
  - kind: point_lookup
    field: roll_id
    weight: 0.55
  - kind: filter
    field: department
    weight: 0.30
    selectivity: 0.08
  - kind: range_scan
    field: year
    weight: 0.15
    selectivity: 0.25
constraints:
  memory_mb: 96
  p99_latency_us: 260
  update_rate: 85
objective:
  latency: 1.0
  memory: 0.15
  update: 0.20
  build: 0.05`
  },
  {
    id: "inventory",
    eyebrow: "STOCK MANAGEMENT",
    title: "Store inventory",
    copy: "Find products by SKU, filter low-stock groups, and scan items by price.",
    spec: `version: mws-0.1
name: store_inventory
record_count: 180000
fields:
  - name: sku
    type: string
    cardinality: 180000
  - name: category
    type: string
    cardinality: 650
  - name: price
    type: uint32
    cardinality: 12000
queries:
  - kind: point_lookup
    field: sku
    weight: 0.50
  - kind: filter
    field: category
    weight: 0.30
    selectivity: 0.015
  - kind: range_scan
    field: price
    weight: 0.20
    selectivity: 0.07
constraints:
  memory_mb: 128
  p99_latency_us: 250
  update_rate: 120
objective:
  latency: 1.0
  memory: 0.15
  update: 0.20
  build: 0.05`
  },
  {
    id: "hospital",
    eyebrow: "HEALTHCARE RECORDS",
    title: "Hospital appointments",
    copy: "Look up appointments, filter by clinic, and scan visit times.",
    spec: `version: mws-0.1
name: hospital_appointments
record_count: 80000
fields:
  - name: appointment_id
    type: uint64
    cardinality: 80000
  - name: clinic
    type: string
    cardinality: 40
  - name: visit_timestamp
    type: uint64
    cardinality: 80000
queries:
  - kind: point_lookup
    field: appointment_id
    weight: 0.50
  - kind: filter
    field: clinic
    weight: 0.25
    selectivity: 0.025
  - kind: range_scan
    field: visit_timestamp
    weight: 0.25
    selectivity: 0.04
constraints:
  memory_mb: 96
  p99_latency_us: 320
  update_rate: 70
objective:
  latency: 1.0
  memory: 0.15
  update: 0.20
  build: 0.05`
  },
  {
    id: "banking",
    eyebrow: "FINANCIAL TRANSACTIONS",
    title: "Transaction explorer",
    copy: "Find transactions by reference, filter by status, and scan amount ranges.",
    spec: `version: mws-0.1
name: transaction_explorer
record_count: 850000
fields:
  - name: transaction_id
    type: uint64
    cardinality: 850000
  - name: status
    type: string
    cardinality: 12
  - name: amount_cents
    type: uint64
    cardinality: 150000
queries:
  - kind: point_lookup
    field: transaction_id
    weight: 0.58
  - kind: filter
    field: status
    weight: 0.22
    selectivity: 0.05
  - kind: range_scan
    field: amount_cents
    weight: 0.20
    selectivity: 0.02
constraints:
  memory_mb: 384
  p99_latency_us: 340
  update_rate: 250
objective:
  latency: 1.0
  memory: 0.15
  update: 0.20
  build: 0.05`
  },
  {
    id: "library",
    eyebrow: "LIBRARY SYSTEM",
    title: "Library catalog",
    copy: "Search by book ID, filter by genre, and browse publication years.",
    spec: `version: mws-0.1
name: library_catalog
record_count: 240000
fields:
  - name: book_id
    type: uint64
    cardinality: 240000
  - name: genre
    type: string
    cardinality: 110
  - name: year_published
    type: uint32
    cardinality: 200
queries:
  - kind: point_lookup
    field: book_id
    weight: 0.46
  - kind: filter
    field: genre
    weight: 0.38
    selectivity: 0.035
  - kind: range_scan
    field: year_published
    weight: 0.16
    selectivity: 0.2
constraints:
  memory_mb: 192
  p99_latency_us: 300
  update_rate: 30
objective:
  latency: 1.0
  memory: 0.15
  update: 0.20
  build: 0.05`
  },
  {
    id: "delivery",
    eyebrow: "DELIVERY OPERATIONS",
    title: "Parcel tracking",
    copy: "Track parcels by ID, filter by location, and search delivery-time windows.",
    spec: `version: mws-0.1
name: parcel_tracking
record_count: 500000
fields:
  - name: parcel_id
    type: string
    cardinality: 500000
  - name: hub
    type: string
    cardinality: 80
  - name: eta_minute
    type: uint64
    cardinality: 480000
queries:
  - kind: point_lookup
    field: parcel_id
    weight: 0.65
  - kind: filter
    field: hub
    weight: 0.15
    selectivity: 0.035
  - kind: range_scan
    field: eta_minute
    weight: 0.20
    selectivity: 0.025
constraints:
  memory_mb: 320
  p99_latency_us: 280
  update_rate: 400
objective:
  latency: 1.0
  memory: 0.15
  update: 0.20
  build: 0.05`
  },
  {
    id: "iot",
    eyebrow: "INDUSTRIAL IOT",
    title: "Sensor readings",
    copy: "Find a reading by ID, filter by machine, and scan time windows.",
    spec: `version: mws-0.1
name: factory_sensor_stream
record_count: 1000000
fields:
  - name: reading_id
    type: uint64
    cardinality: 1000000
  - name: machine_id
    type: uint32
    cardinality: 250
  - name: timestamp
    type: uint64
    cardinality: 1000000
queries:
  - kind: point_lookup
    field: reading_id
    weight: 0.15
  - kind: filter
    field: machine_id
    weight: 0.35
    selectivity: 0.004
  - kind: range_scan
    field: timestamp
    weight: 0.50
    selectivity: 0.03
constraints:
  memory_mb: 512
  p99_latency_us: 550
  update_rate: 900
objective:
  latency: 1.0
  memory: 0.15
  update: 0.20
  build: 0.05`
  },
  {
    id: "support",
    eyebrow: "SUPPORT WORKFLOWS",
    title: "Customer support cases",
    copy: "Find a ticket, filter by priority, and scan case-creation dates.",
    spec: `version: mws-0.1
name: support_cases
record_count: 100000
fields:
  - name: ticket_id
    type: uint64
    cardinality: 100000
  - name: priority
    type: string
    cardinality: 5
  - name: created_at
    type: uint64
    cardinality: 100000
queries:
  - kind: point_lookup
    field: ticket_id
    weight: 0.42
  - kind: filter
    field: priority
    weight: 0.35
    selectivity: 0.2
  - kind: range_scan
    field: created_at
    weight: 0.23
    selectivity: 0.08
constraints:
  memory_mb: 128
  p99_latency_us: 275
  update_rate: 150
objective:
  latency: 1.0
  memory: 0.15
  update: 0.20
  build: 0.05`
  },
  {
    id: "social",
    eyebrow: "COMMUNITY APPS",
    title: "Social posts",
    copy: "Find posts by ID, filter by category, and scan published times.",
    spec: `version: mws-0.1
name: social_posts
record_count: 400000
fields:
  - name: post_id
    type: uint64
    cardinality: 400000
  - name: category
    type: string
    cardinality: 65
  - name: published_at
    type: uint64
    cardinality: 400000
queries:
  - kind: point_lookup
    field: post_id
    weight: 0.35
  - kind: filter
    field: category
    weight: 0.30
    selectivity: 0.04
  - kind: range_scan
    field: published_at
    weight: 0.35
    selectivity: 0.05
constraints:
  memory_mb: 256
  p99_latency_us: 390
  update_rate: 150
objective:
  latency: 1.0
  memory: 0.15
  update: 0.20
  build: 0.05`
  },
  {
    id: "jobs",
    eyebrow: "RECRUITMENT",
    title: "Job applications",
    copy: "Find applications, filter by role, and scan application dates.",
    spec: `version: mws-0.1
name: job_applications
record_count: 130000
fields:
  - name: application_id
    type: uint64
    cardinality: 130000
  - name: role
    type: string
    cardinality: 95
  - name: applied_at
    type: uint64
    cardinality: 130000
queries:
  - kind: point_lookup
    field: application_id
    weight: 0.40
  - kind: filter
    field: role
    weight: 0.35
    selectivity: 0.025
  - kind: range_scan
    field: applied_at
    weight: 0.25
    selectivity: 0.08
constraints:
  memory_mb: 128
  p99_latency_us: 300
  update_rate: 100
objective:
  latency: 1.0
  memory: 0.15
  update: 0.20
  build: 0.05`
  },
  {
    id: "attendance",
    eyebrow: "ACADEMIC ADMINISTRATION",
    title: "Class attendance",
    copy: "Find a student attendance entry, filter by class, and scan session dates.",
    spec: `version: mws-0.1
name: attendance_tracker
record_count: 60000
fields:
  - name: entry_id
    type: uint64
    cardinality: 60000
  - name: class_id
    type: uint32
    cardinality: 80
  - name: session_date
    type: uint32
    cardinality: 500
queries:
  - kind: point_lookup
    field: entry_id
    weight: 0.55
  - kind: filter
    field: class_id
    weight: 0.25
    selectivity: 0.02
  - kind: range_scan
    field: session_date
    weight: 0.20
    selectivity: 0.1
constraints:
  memory_mb: 64
  p99_latency_us: 230
  update_rate: 90
objective:
  latency: 1.0
  memory: 0.15
  update: 0.20
  build: 0.05`
  },
  {
    id: "restaurant",
    eyebrow: "FOOD PLATFORMS",
    title: "Restaurant orders",
    copy: "Find orders by ID, filter by outlet, and scan order placement times.",
    spec: `version: mws-0.1
name: restaurant_orders
record_count: 300000
fields:
  - name: order_id
    type: uint64
    cardinality: 300000
  - name: outlet_id
    type: uint32
    cardinality: 350
  - name: ordered_at
    type: uint64
    cardinality: 300000
queries:
  - kind: point_lookup
    field: order_id
    weight: 0.60
  - kind: filter
    field: outlet_id
    weight: 0.25
    selectivity: 0.015
  - kind: range_scan
    field: ordered_at
    weight: 0.15
    selectivity: 0.025
constraints:
  memory_mb: 192
  p99_latency_us: 240
  update_rate: 210
objective:
  latency: 1.0
  memory: 0.15
  update: 0.20
  build: 0.05`
  }
] as const
