import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import ts from 'typescript';

// Use the existing TypeScript dependency so these tests also run on Node 20.
const source = await readFile(new URL('../src/lib/summary-engine.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
});
const {
  executeClientAIQuery, generateLLMSummary, saveLLMConfig, loadLLMConfig,
  clearLLMConfig, DEFAULT_ANTHROPIC_MODEL,
} = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

const nodes = [
  { id: 1, name: 'UserController', type: 'Class', filePath: 'src/users.ts' },
  { id: 'db', name: 'Database', type: 'Class', filePath: 'src/db.ts' },
];
const links = [{ source: nodes[0], target: nodes[1], type: 'CALLS' }];
const config = { provider: 'anthropic', apiKey: 'test-anthropic-key' };
const answer = { explanation: 'UserController calls Database.', nodeIds: [1, 'db'] };

function mockResponse(t, data, status = 200, statusText = '') {
  return t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(data), {
    status, statusText, headers: { 'Content-Type': 'application/json' },
  }));
}

test('Anthropic graph queries send the browser API contract and parse text blocks', async (t) => {
  const text = JSON.stringify(answer);
  const fetch = mockResponse(t, {
    stop_reason: 'end_turn',
    content: [
      { type: 'thinking', thinking: 'Not part of the answer' },
      { type: 'text', text: text.slice(0, 30) },
      { type: 'text', text: text.slice(30) },
    ],
  });

  const result = await executeClientAIQuery('Who calls the database?', nodes, links, config);
  assert.equal(result.success, true);
  assert.equal(result.explanation, answer.explanation);
  assert.deepEqual(result.nodes, [{ id: 1 }, { id: 'db' }]);
  assert.equal(fetch.mock.callCount(), 1);

  const [url, options] = fetch.mock.calls[0].arguments;
  assert.equal(url, 'https://api.anthropic.com/v1/messages');
  assert.equal(options.method, 'POST');
  assert.equal(options.headers.Authorization, `Bearer ${config.apiKey}`);
  assert.equal(options.headers['anthropic-version'], '2026-10-21');
  assert.equal(options.headers['anthropic-dangerous-direct-browser-access'], 'true');
  assert.ok(!options.body.includes(config.apiKey));
  const body = JSON.parse(options.body);
  assert.equal(body.model, DEFAULT_ANTHROPIC_MODEL);
  assert.equal(body.max_tokens, 2000);
  assert.equal(body.messages[0].role, 'user');
  assert.match(body.messages[0].content, /Who calls the database/);
  assert.match(body.messages[0].content, /"source":1,"target":"db"/);
  assert.equal(body.output_config.format.type, 'json_schema');
  assert.deepEqual(body.output_config.format.schema.required, ['explanation', 'nodeIds']);
  assert.equal(body.output_config.format.schema.additionalProperties, false);
  assert.equal(body.temperature, undefined);
});

test('Anthropic summaries use a custom model and plain text output', async (t) => {
  const fetch = mockResponse(t, { content: [{ type: 'text', text: 'Handles users.' }] });
  const result = await generateLLMSummary(nodes[0], nodes, links, {
    ...config, apiKey: ` ${config.apiKey} `, model: ' claude-haiku-4-5 ',
  });
  assert.equal(result, 'Handles users.');
  const [, options] = fetch.mock.calls[0].arguments;
  const body = JSON.parse(options.body);
  assert.equal(options.headers.Authorization, `Bearer ${config.apiKey}`);
  assert.equal(body.model, 'claude-haiku-4-5');
  assert.equal(body.max_tokens, 200);
  assert.equal(body.output_config, undefined);
});

test('a blank custom model falls back to the default', async (t) => {
  const fetch = mockResponse(t, { content: [{ type: 'text', text: 'Handles users.' }] });
  await generateLLMSummary(nodes[0], nodes, links, { ...config, model: '   ' });
  assert.equal(JSON.parse(fetch.mock.calls[0].arguments[1].body).model, DEFAULT_ANTHROPIC_MODEL);
});

for (const [status, message] of [[401, 'Invalid API key'], [429, 'Rate limit exceeded']]) {
  test(`Anthropic ${status} errors reach the query UI and summaries fall back`, async (t) => {
    t.mock.method(console, 'error', () => {});
    mockResponse(t, { error: { message } }, status);
    const result = await executeClientAIQuery('Explain the graph', nodes, links, config);
    assert.equal(result.success, false);
    assert.equal(result.error, `Anthropic API error: ${status} — ${message}`);
    assert.equal(await generateLLMSummary(nodes[0], nodes, links, config), null);
  });
}

test('non-JSON API errors produce a useful message', async (t) => {
  t.mock.method(console, 'error', () => {});
  t.mock.method(globalThis, 'fetch', async () => new Response('Service unavailable', {
    status: 503, statusText: 'Service Unavailable',
  }));
  const result = await executeClientAIQuery('Explain the graph', nodes, links, config);
  assert.equal(result.success, false);
  assert.equal(result.error, 'Anthropic API error: 503 — Service Unavailable');
});

for (const [response, expected] of [
  [{ stop_reason: 'max_tokens', content: [{ type: 'text', text: '{"explanation":' }] }, /response limit/],
  [{ stop_reason: 'refusal', content: [{ type: 'text', text: 'Cannot help.' }] }, /declined/],
  [{ content: [{ type: 'thinking', thinking: 'No answer' }, null] }, /empty response/],
  [{ content: 'invalid' }, /empty response/],
  [{ content: [{ type: 'text', text: 'not JSON' }] }, /JSON/],
]) {
  test(`rejects unusable Anthropic responses (${expected.source})`, async (t) => {
    t.mock.method(console, 'error', () => {});
    mockResponse(t, response);
    const result = await executeClientAIQuery('Explain the graph', nodes, links, config);
    assert.equal(result.success, false);
    assert.match(result.error, expected);
  });
}

test('network failures return an error result', async (t) => {
  t.mock.method(console, 'error', () => {});
  t.mock.method(globalThis, 'fetch', async () => { throw new Error('Failed to fetch'); });
  const result = await executeClientAIQuery('Explain the graph', nodes, links, config);
  assert.equal(result.success, false);
  assert.equal(result.error, 'Failed to fetch');
});

for (const provider of ['gemini', 'mistral']) {
  test(`${provider} queries continue to use their existing API`, async (t) => {
    const text = JSON.stringify(answer);
    const fetch = mockResponse(t, provider === 'gemini'
      ? { candidates: [{ content: { parts: [{ text }] } }] }
      : { choices: [{ message: { content: text } }] });
    const result = await executeClientAIQuery('Explain the graph', nodes, links, { ...config, provider });
    assert.equal(result.success, true);
    assert.equal(result.explanation, answer.explanation);
    const [url, options] = fetch.mock.calls[0].arguments;
    assert.match(url, provider === 'gemini' ? /generativelanguage.googleapis.com/ : /api.mistral.ai/);
    assert.equal(options.headers['anthropic-dangerous-direct-browser-access'], undefined);
  });
}

test('Anthropic configuration persists and can be cleared', (t) => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  const values = new Map();
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      setItem: (key, value) => values.set(key, value),
      getItem: (key) => values.get(key) ?? null,
      removeItem: (key) => values.delete(key),
    },
  });
  t.after(() => {
    if (original) Object.defineProperty(globalThis, 'localStorage', original);
    else delete globalThis.localStorage;
  });
  const saved = { ...config, model: 'claude-haiku-4-5' };
  saveLLMConfig(saved);
  assert.deepEqual(loadLLMConfig(), saved);
  clearLLMConfig();
  assert.deepEqual(loadLLMConfig(), { provider: 'none', apiKey: '' });
});
