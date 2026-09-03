const fs = require('fs');
const path = '/app/packages/twenty-server/dist/front/assets/SettingsAiModelsTable-DGpMzVjh.js';
let content = fs.readFileSync(path, 'utf8');

// Grid templates: Provider(100px) + Model(1fr) + Frontier(56px) + Cost(90px) + Checkbox(40px) [+ Actions(32px)]
// with provider:    "100px 1fr 56px 90px 40px"      (no actions)
// with provider+actions: "100px 1fr 56px 90px 40px 32px"
// without provider: "1fr 56px 90px 40px"
// without provider+actions: "1fr 56px 90px 40px 32px"
const OLD_GRIDS = 'xe="1fr 100px 120px 40px",fe="1fr 100px 40px",ve="1fr 100px 120px 40px 32px",he="1fr 100px 40px 32px"';
const NEW_GRIDS = 'xe="100px 1fr 56px 90px 40px",fe="100px 1fr 56px 90px 40px",ve="100px 1fr 56px 90px 40px 32px",he="100px 1fr 56px 90px 40px 32px"';
content = content.replace(OLD_GRIDS, NEW_GRIDS);

// Header row: currently Model, Cost/1M, Provider, Checkbox
// Want: Provider, Model, Frontier, Cost/1M, Checkbox
const OLD_HEADER = '(0,e.jsx)(v,{children:(0,e.jsx)(C,{id:"6YtxFj"})}),(0,e.jsx)(v,{align:"right",children:(0,e.jsx)("span",{style:{fontSize:"11px",color:"inherit"},children:"Cost / 1M"})}),m&&(0,e.jsx)(v,{align:"right",children:(0,e.jsx)(C,{id:"aemBRq"})}),(0,e.jsx)(v,{align:"right",children:t(_)&&(0,e.jsx)(A,{checked:g,indeterminate:!g&&!L,onChange:()=>_(!g)})})';
const NEW_HEADER = 'm&&(0,e.jsx)(v,{children:(0,e.jsx)("span",{style:{fontSize:"11px"},children:"Provider"})}),(0,e.jsx)(v,{children:(0,e.jsx)(C,{id:"6YtxFj"})}),(0,e.jsx)(v,{align:"center",children:(0,e.jsx)("span",{style:{fontSize:"11px"},children:"Frontier"})}),(0,e.jsx)(v,{align:"right",children:(0,e.jsx)("span",{style:{fontSize:"11px"},children:"Cost /1M in"})}),(0,e.jsx)(v,{align:"right",children:t(_)&&(0,e.jsx)(A,{checked:g,indeterminate:!g&&!L,onChange:()=>_(!g)})})';
content = content.replace(OLD_HEADER, NEW_HEADER);

// Data rows: currently Model cell, Cost cell, Provider cell, Checkbox cell
// Want: Provider cell, Model cell, Frontier cell, Cost cell, Checkbox cell
const OLD_ROWS = '(0,e.jsx)(f,{color:d?h.font.color.light:h.font.color.primary,children:(0,e.jsxs)(ue,{children:[(0,e.jsx)(E,{size:x.icon.size.md,stroke:x.icon.stroke.sm,color:d?x.font.color.light:x.font.color.secondary}),(0,e.jsx)(Ie,{children:s.label}),d&&s.isDeprecated&&(0,e.jsxs)(je,{children:["· ",(0,e.jsx)(C,{id:"Ssdrw4"})]})]})}),m&&(0,e.jsx)(f,{align:"right",color:h.font.color.tertiary,children:Se(s)}),(0,e.jsx)(f,{align:"right",onClick:y=>y.stopPropagation(),children:(0,e.jsx)(A,{checked:S,disabled:d,onChange:()=>p(s.modelId,S)})})';
const NEW_ROWS = 'm&&(0,e.jsx)(f,{color:h.font.color.tertiary,children:(0,e.jsx)("span",{style:{fontSize:"12px",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"},children:Se(s)})}),(0,e.jsx)(f,{color:d?h.font.color.light:h.font.color.primary,children:(0,e.jsxs)(ue,{children:[(0,e.jsx)(E,{size:x.icon.size.md,stroke:x.icon.stroke.sm,color:d?x.font.color.light:x.font.color.secondary}),(0,e.jsx)(Ie,{children:s.label.replace(/^★\\s*/,"")}),d&&s.isDeprecated&&(0,e.jsxs)(je,{children:["· ",(0,e.jsx)(C,{id:"Ssdrw4"})]})]})},),(0,e.jsx)(f,{align:"center",children:(0,e.jsx)("span",{style:{fontSize:"13px",color:s.label.startsWith("★")?"#e05d3d":"#444"},children:s.label.startsWith("★")?"★":"—"})}),(0,e.jsx)(f,{align:"right",children:(0,e.jsx)("span",{style:{fontSize:"11px",fontFamily:"monospace",color:h.font.color.tertiary},children:s.inputCostPerMillionTokens!=null?("$"+s.inputCostPerMillionTokens.toFixed(2)):"—"})}),(0,e.jsx)(f,{align:"right",onClick:y=>y.stopPropagation(),children:(0,e.jsx)(A,{checked:S,disabled:d,onChange:()=>p(s.modelId,S)})})';
content = content.replace(OLD_ROWS, NEW_ROWS);

fs.writeFileSync(path, content);
console.log('Patched. Grid:', content.match(/xe="[^"]+"/)[0]);
console.log('Header patched:', content.includes('Frontier'));
console.log('Row patched:', content.includes('startsWith("★")'));
