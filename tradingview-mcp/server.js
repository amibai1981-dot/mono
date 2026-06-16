import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { chromium } from "playwright";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import dotenv from "dotenv";

dotenv.config();

const __dir = dirname(fileURLToPath(import.meta.url));
const uaeStocks = JSON.parse(readFileSync(join(__dir, "uae-stocks.json"), "utf8"));
const rules = JSON.parse(readFileSync(join(__dir, "rules.json"), "utf8"));

let browser = null;
let page = null;

async function getBrowser() {
  if (!browser) {
    browser = await chromium.launch({ headless: false });
    const ctx = await browser.newContext({ locale: "en-US" });
    page = await ctx.newPage();
  }
  return page;
}

async function fetchChartData(symbol, timeframe = "15") {
  const p = await getBrowser();
  const url = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}&interval=${timeframe}`;
  await p.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
  await p.waitForTimeout(4000);

  return await p.evaluate((sym) => {
    const getText = (sel) => document.querySelector(sel)?.innerText?.trim() || null;
    return {
      symbol: sym,
      title: document.title,
      url: window.location.href,
      legend: Array.from(document.querySelectorAll('[data-name="legend-series-item"]')).map(el => el.innerText),
      price: getText('.tv-symbol-price-quote__value') || getText('[data-field="last_price"]'),
      change: getText('.tv-symbol-price-quote__change-value'),
      timestamp: new Date().toISOString(),
    };
  }, symbol);
}

async function fetchQuote(symbol) {
  const p = await getBrowser();
  const slug = symbol.replace("DFM:", "").replace("ADX:", "");
  await p.goto(`https://www.tradingview.com/symbols/${slug}/`, { waitUntil: "domcontentloaded", timeout: 15000 });
  await p.waitForTimeout(2000);

  return await p.evaluate((sym) => ({
    symbol: sym,
    price: document.querySelector('.tv-symbol-price-quote__value')?.innerText?.trim() || "N/A",
    change: document.querySelector('.tv-symbol-price-quote__change-value')?.innerText?.trim() || "N/A",
    timestamp: new Date().toISOString(),
  }), symbol);
}

// ───── MCP Server ─────

const server = new Server(
  { name: "tradingview-mcp", version: "2.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "get_chart_data",
      description: "اقرأ بيانات مخطط TradingView لأي رمز (أسهم إماراتية أو كريبتو)",
      inputSchema: {
        type: "object",
        properties: {
          symbol: { type: "string", description: "مثل: DFM:EMAAR أو BTCUSDT" },
          timeframe: { type: "string", description: "1 | 5 | 15 | 60 | D", default: "15" },
        },
        required: ["symbol"],
      },
    },
    {
      name: "get_quote",
      description: "السعر الحالي وتغيير اليوم",
      inputSchema: {
        type: "object",
        properties: {
          symbol: { type: "string" },
        },
        required: ["symbol"],
      },
    },
    {
      name: "analyze_scalp",
      description: "تحليل فرصة سكالب مع إشارة واضحة: شراء / بيع / انتظار",
      inputSchema: {
        type: "object",
        properties: {
          symbol: { type: "string", description: "رمز الأصل" },
          capital: { type: "number", description: "رأس المال بالدرهم أو USDT (اختياري)" },
        },
        required: ["symbol"],
      },
    },
    {
      name: "morning_brief",
      description: "تقرير صباحي: اتجاه كل أصل في قائمة المراقبة",
      inputSchema: {
        type: "object",
        properties: {
          market: { type: "string", description: "uae | crypto | all", default: "all" },
        },
      },
    },
    {
      name: "scan_uae_market",
      description: "مسح سريع لكل الأسهم الإماراتية في القائمة وإيجاد أفضل فرصة سكالب",
      inputSchema: {
        type: "object",
        properties: {
          min_change_pct: { type: "number", description: "أقل تغيير مطلوب %", default: 0.5 },
        },
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === "get_chart_data") {
      const data = await fetchChartData(args.symbol, args.timeframe || "15");
      return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
    }

    if (name === "get_quote") {
      const q = await fetchQuote(args.symbol);
      return { content: [{ type: "text", text: JSON.stringify(q, null, 2) }] };
    }

    if (name === "analyze_scalp") {
      const [chart5, chart15] = await Promise.all([
        fetchChartData(args.symbol, "5"),
        fetchChartData(args.symbol, "15"),
      ]);
      const result = {
        symbol: args.symbol,
        strategy: rules.strategy.name,
        entryRules: rules.strategy.entry_rules,
        risk: rules.strategy.risk_management,
        chart_5m: chart5,
        chart_15m: chart15,
        capital: args.capital ? `${args.capital} (درهم أو USDT)` : "غير محدد",
        instruction: "حلّل البيانات أعلاه بناءً على قواعد الاستراتيجية وأعطِ إشارة واضحة مع نقطة دخول و Stop Loss وهدف ربح",
      };
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }

    if (name === "morning_brief") {
      const market = args.market || "all";
      const results = [];

      if (market === "uae" || market === "all") {
        for (const stock of uaeStocks.watchlist) {
          const q = await fetchQuote(stock.symbol);
          results.push({ ...stock, ...q });
        }
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            brief: results,
            session: uaeStocks.session,
            generatedAt: new Date().toISOString(),
          }, null, 2),
        }],
      };
    }

    if (name === "scan_uae_market") {
      const minChange = args.min_change_pct || 0.5;
      const scanned = [];

      for (const stock of uaeStocks.watchlist) {
        const q = await fetchQuote(stock.symbol);
        const changePct = parseFloat(q.change) || 0;
        scanned.push({ ...stock, ...q, changePct, potential: Math.abs(changePct) >= minChange });
      }

      const opportunities = scanned.filter(s => s.potential);
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            scanned: scanned.length,
            opportunities,
            best: opportunities.sort((a, b) => Math.abs(b.changePct) - Math.abs(a.changePct))[0] || null,
            timestamp: new Date().toISOString(),
          }, null, 2),
        }],
      };
    }

    throw new Error(`أداة غير معروفة: ${name}`);
  } catch (err) {
    return { content: [{ type: "text", text: `خطأ: ${err.message}` }], isError: true };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
console.error("✅ TradingView MCP v2 — جاهز (أسهم إماراتية + كريبتو)");
