import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 10,  // Number of virtual users
  duration: '5m',  // Test duration
  thresholds: {
    'http_req_duration': ['p(95)<500'],  // 95% of requests should be below 500ms
    'http_req_failed': ['rate<0.01'],    // Less than 1% of requests should fail
  },
};

const BASE_URL = 'https://jupyter.${DOMAIN}';
const TOKEN = __ENV.HUB_TOKEN;  // JupyterHub API token

export default function () {
  // Start a new server
  const startServer = http.post(`${BASE_URL}/hub/api/users/test-user/server`, null, {
    headers: {
      'Authorization': `token ${TOKEN}`,
    },
  });
  
  check(startServer, {
    'server start requested': (r) => r.status === 201 || r.status === 202,
  });

  // Wait for server to be ready
  let ready = false;
  for (let i = 0; i < 30; i++) {
    const status = http.get(`${BASE_URL}/hub/api/users/test-user`, {
      headers: {
        'Authorization': `token ${TOKEN}`,
      },
    });
    
    const serverReady = status.json('server') !== null;
    if (serverReady) {
      ready = true;
      break;
    }
    
    sleep(1);
  }

  check(ready, {
    'server started successfully': (r) => r === true,
  });

  // Stop the server
  const stopServer = http.delete(`${BASE_URL}/hub/api/users/test-user/server`, null, {
    headers: {
      'Authorization': `token ${TOKEN}`,
    },
  });
  
  check(stopServer, {
    'server stopped': (r) => r.status === 204,
  });

  sleep(1);
} 