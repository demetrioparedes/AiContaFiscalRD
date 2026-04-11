const token = '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';
const page_id = '3324332f-8b18-805c-b67e-d93abed9cd91';
const headers = {
  'Authorization': `Bearer ${token}`,
  'Notion-Version': '2022-06-28',
  'Content-Type': 'application/json'
};

const dbs = [
  {
    "title": [{ "type": "text", "text": { "content": "🗓️ 01. Roadmap de Hitos" } }],
    "properties": {
      "Hito": { "title": {} },
      "Fecha Entrega": { "date": {} },
      "Estado": { "status": {} },
      "Prioridad": { "select": { "options": [
        { "name": "Crítico", "color": "red" },
        { "name": "Alto", "color": "orange" },
        { "name": "Medio", "color": "yellow" }
      ] } }
    }
  },
  {
    "title": [{ "type": "text", "text": { "content": "⚠️ 02. Matriz de Riesgos" } }],
    "properties": {
      "Riesgo": { "title": {} },
      "Probabilidad": { "select": { "options": [
        { "name": "Alta", "color": "red" },
        { "name": "Media", "color": "yellow" },
        { "name": "Baja", "color": "green" }
      ] } },
      "Impacto": { "select": { "options": [
        { "name": "Catastrófico", "color": "red" },
        { "name": "Significativo", "color": "orange" },
        { "name": "Menor", "color": "blue" }
      ] } },
      "Estado de Mitigación": { "status": {} }
    }
  },
  {
    "title": [{ "type": "text", "text": { "content": "📝 03. Minutas de Reuniones" } }],
    "properties": {
      "Sesión": { "title": {} },
      "Fecha": { "date": {} },
      "Participantes": { "multi_select": { "options": [{ "name": "AI Agent" }, { "name": "Lead Expert" }] } },
      "Pendientes": { "checkbox": {} }
    }
  },
  {
    "title": [{ "type": "text", "text": { "content": "✅ 04. Tablero de Tareas" } }],
    "properties": {
      "Tarea": { "title": {} },
      "Estado": { "status": {} },
      "Prioridad": { "select": { "options": [{ "name": "Alta", "color": "red" }, { "name": "Media", "color": "yellow" }, { "name": "Baja", "color": "blue" }] } }
    }
  },
  {
    "title": [{ "type": "text", "text": { "content": "📖 05. Bitácora del Proyecto" } }],
    "properties": {
      "Sesión": { "title": {} },
      "Fecha": { "date": {} },
      "Resumen": { "rich_text": {} }
    }
  },
  {
    "title": [{ "type": "text", "text": { "content": "📂 06. Documentación y Recursos" } }],
    "properties": {
      "Nombre": { "title": {} },
      "Tipo": { "select": { "options": [{ "name": "DGII" }, { "name": "Técnica" }, { "name": "Legal" }] } },
      "Enlace": { "url": {} }
    }
  }
];

async function run() {
  for (const db of dbs) {
    const payload = { parent: { type: "page_id", page_id }, ...db };
    const response = await fetch('https://api.notion.com/v1/databases', {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    });
    const res = await response.json();
    if (response.ok) console.log(`Created: ${db.title[0].text.content}`);
    else console.error(`Error:`, res);
  }
}

run();
