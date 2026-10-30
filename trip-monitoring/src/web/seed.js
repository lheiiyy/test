// Dummy data only, same as tests/fixtures/seed.json (a test keeps them equal).
window.TM_SEED = {
  "users": [
    {
      "id": "USR-0001",
      "name": "Test Requestor",
      "role": "requestor",
      "team_id": "TEM-0001"
    },
    {
      "id": "USR-0002",
      "name": "Test Driver",
      "role": "driver",
      "team_id": "TEM-0001"
    },
    {
      "id": "USR-0003",
      "name": "Test Supervisor",
      "role": "supervisor",
      "team_id": "TEM-0001"
    },
    {
      "id": "USR-0004",
      "name": "Test Accounting",
      "role": "accounting",
      "team_id": "TEM-0001"
    },
    {
      "id": "USR-0005",
      "name": "Test Admin",
      "role": "admin",
      "team_id": "TEM-0001"
    }
  ],
  "teams": [
    {
      "id": "TEM-0001",
      "name": "Sample Team"
    }
  ],
  "vehicles": [
    {
      "id": "VEH-0001",
      "plate": "TEST-001",
      "description": "Sample van (fake)"
    }
  ],
  "lookups": [
    {
      "id": "LKP-0001",
      "group": "meta",
      "key": "schema_version",
      "value": "1"
    }
  ]
};
