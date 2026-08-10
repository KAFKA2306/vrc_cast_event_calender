const fs=require('fs');
const assert=require('assert');

const index=fs.readFileSync('tonight/index.html','utf8');
const organic=fs.readFileSync('tonight/tonight.js','utf8');
const featured=fs.readFileSync('tonight/featured-tonight.js','utf8');
const css=fs.readFileSync('tonight/featured-tonight.css','utf8');
const manifest=JSON.parse(fs.readFileSync('sponsorships.json','utf8'));
const kpi=JSON.parse(fs.readFileSync('metrics/featured-tonight-kpi.json','utf8'));

assert(index.includes('featured-tonight.css'));
assert(index.includes('featured-tonight.js'));
assert(featured.includes("'スポンサー掲載'"));
assert(featured.includes("featured-tonight.metric.v1"));
assert(featured.includes("'impression'"));
assert(featured.includes("'outbound_click'"));
assert(featured.includes("sessionStorage.getItem('featured-tonight-metrics')"));
assert(featured.includes("window.parent.postMessage"));
assert(css.includes('.featured-rail'));
assert(css.includes('.sponsor-label'));
assert(!organic.includes('sponsorship'));
assert(!organic.includes('campaign_id'));
assert.strictEqual(manifest.schema_version,'featured-tonight.v1');
assert.deepStrictEqual(manifest.campaigns,[]);
assert.strictEqual(kpi.status,'NOT_STARTED');
assert.deepStrictEqual(kpi.evidence,[]);
for(const value of Object.values(kpi.metrics))assert.strictEqual(value,0);
console.log('featured-tonight contract: OK');
