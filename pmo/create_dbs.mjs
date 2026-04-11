import { readFileSync } from 'fs';

const token = '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';
const headers = {
  'Authorization': `Bearer ${token}`,
  'Notion-Version': '2022-06-28',
  'Content-Type': 'application/json'
};

async function run() {
  for (const file of ['db1.json', 'db2.json', 'db3.json']) {
    const data = readFileSync(file, 'utf8');
    const response = await fetch('https://api.notion.com/v1/databases', {
      method: 'POST',
      headers,
      body: data
    });
    const resJson = await response.json();
    if (response.ok) {
      console.log(`Created DB from ${file}, URL: ${resJson.url}`);
    } else {
      console.error(`Error for ${file}:`, resJson);
    }
  }
}

run();
