"""Static HTML/CSS/JS for the SLA Command Center page (kept dependency-free)."""

PAGE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>SLA Command Center - Daily Guard</title>
<style>
  :root { --bg:#0f1525; --panel:#161f36; --line:#243355; --txt:#e8eefc; --muted:#8aa0c8;
          --green:#1faa6b; --amber:#e0a324; --red:#e0524a; --grey:#5a6a8c; --accent:#4f8cff; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
         background:var(--bg); color:var(--txt); }
  header { padding:18px 26px; border-bottom:1px solid var(--line);
           display:flex; align-items:center; gap:16px; }
  header h1 { font-size:18px; margin:0; }
  header .sub { color:var(--muted); font-size:13px; }
  .wrap { padding:22px 26px; }
  .legend { display:flex; gap:18px; color:var(--muted); font-size:12px; margin-bottom:14px; flex-wrap:wrap; }
  .chip { display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; font-weight:600; }
  .OnTrack { background:rgba(31,170,107,.16); color:#4ad99a; }
  .AtRisk  { background:rgba(224,163,36,.16); color:#f2c75c; }
  .Breached{ background:rgba(224,82,74,.16);  color:#ff7b73; }
  .Unknown { background:rgba(138,160,200,.16);color:#aab8d6; }
  table { width:100%; border-collapse:collapse; background:var(--panel);
          border:1px solid var(--line); border-radius:12px; overflow:hidden; }
  th,td { text-align:left; padding:12px 14px; border-bottom:1px solid var(--line); font-size:14px; }
  th { color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
  tr:last-child td { border-bottom:none; }
  .lane { font-size:12px; padding:2px 8px; border-radius:6px; border:1px solid var(--line); color:var(--muted); }
  .lane.fast { color:#ffd479; border-color:#5b4a1d; background:rgba(224,163,36,.10); }
  .btn { background:var(--accent); color:#fff; border:none; padding:7px 12px; border-radius:8px;
         font-size:13px; cursor:pointer; }
  .btn[disabled] { background:#2a3656; color:#6f80a6; cursor:not-allowed; }
  .factors { color:var(--muted); font-size:12px; margin-top:4px; }
  .muted { color:var(--muted); }
  .panel { margin-top:22px; background:var(--panel); border:1px solid var(--line);
           border-radius:12px; padding:16px; }
  .panel h2 { font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); margin:0 0 10px; }
  .audit { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; white-space:pre-wrap;
           color:#bcd0f5; max-height:240px; overflow:auto; }
  .toast { position:fixed; right:20px; bottom:20px; background:#15233f; border:1px solid var(--line);
           padding:12px 16px; border-radius:10px; font-size:13px; opacity:0; transition:opacity .2s; }
  .toast.show { opacity:1; }
  .tier { font-size:11px; color:var(--muted); }
</style>
</head>
<body>
<header>
  <h1>SLA Command Center</h1>
  <span class="sub">Daily Guard - pilot cohort &middot; trains &amp; lanes view</span>
</header>
<div class="wrap">
  <div class="legend">
    <span><span class="chip OnTrack">OnTrack</span> predicted to make SLA</span>
    <span><span class="chip AtRisk">AtRisk</span> predicted p90 after deadline</span>
    <span><span class="chip Breached">Breached</span> already past</span>
    <span><span class="lane fast">Fast Lane</span> reassigned to higher capacity tier</span>
    <span class="muted">auto-refresh 4s</span>
  </div>

  <table>
    <thead>
      <tr>
        <th>Function</th><th>State</th><th>Predicted finish</th><th>SLA</th>
        <th>Status</th><th>Lane</th><th>Action</th>
      </tr>
    </thead>
    <tbody id="rows"><tr><td colspan="7" class="muted">loading...</td></tr></tbody>
  </table>

  <div class="panel">
    <h2>Beacon Control - audit log (every write is recorded)</h2>
    <div id="audit" class="audit">no actions yet</div>
  </div>
</div>
<div id="toast" class="toast"></div>

<script>
function hhmm(ts){ if(!ts) return "-"; var p=ts.split("T")[1]; return p? p.slice(0,5):ts; }

function factorText(f){
  var d=f.detail||{};
  if(f.type==="file_delay") return "Upstream file "+(d.file||"")+" expected "+(d.expectedBy||"?")+", arrived "+(d.arrivedAt||"?");
  if(f.type==="late_start") return "Late start on "+d.job+" (+"+d.minutes+"m vs "+d.scheduled+")";
  if(f.type==="cascade_delta_minutes") return "Cascade delay +"+d.value+"m";
  if(f.type==="historical_runtime_p90") return "Runtime p90 ~"+d.minutes+"m on "+(d.capacityTier||"?")+" tier";
  return f.type;
}

async function load(){
  var data = await (await fetch("/api/daily-guard")).json();
  var tb = document.getElementById("rows");
  tb.innerHTML = "";
  data.items.forEach(function(r){
    var tr = document.createElement("tr");
    var factors = (r.factors||[]).map(factorText).map(function(t){return "&bull; "+t;}).join("<br>");
    var eligible = r.fast_lane_eligible;
    var fl = r.fast_lane||{};
    var target = fl.target? fl.target.label : "";
    var btn;
    if(r.lane==="fast"){
      btn = '<span class="chip OnTrack">on Fast Lane</span>';
    } else if(eligible){
      btn = '<button class="btn" onclick="moveFastLane(\''+r.function_id+'\',\''+r.run_id+'\')">Move to Fast Lane</button>'
            + '<div class="tier">to '+target+' &middot; ~'+fl.minutesSaved+'m saved</div>';
    } else {
      btn = '<button class="btn" disabled title="'+((fl.reasons||[]).join("; "))+'">Move to Fast Lane</button>';
    }
    tr.innerHTML =
      '<td><b>'+r.display_name+'</b><div class="factors">'+factors+'</div></td>'+
      '<td>'+r.state+'</td>'+
      '<td>'+hhmm(r.predicted_finish_p50)+' <span class="muted">/ p90 '+hhmm(r.predicted_finish_p90)+'</span></td>'+
      '<td>'+(r.sla_deadline_local||hhmm(r.sla_deadline))+'</td>'+
      '<td><span class="chip '+r.sla_status+'">'+r.sla_status+'</span></td>'+
      '<td><span class="lane '+(r.lane==="fast"?"fast":"")+'">'+(r.lane==="fast"?"Fast Lane":"normal")+'</span></td>'+
      '<td>'+btn+'</td>';
    tb.appendChild(tr);
  });
  loadAudit();
}

async function loadAudit(){
  try{
    var a = await (await fetch("/api/audit")).json();
    var el = document.getElementById("audit");
    if(!a.items || !a.items.length){ el.textContent="no actions yet"; return; }
    el.textContent = a.items.map(function(x){
      return x.at+"  "+x.action+"  "+(x.function_id||"")+"  -> "+(x.outcome||"")+
        (x.from_tier? "  ["+x.from_tier+"->"+x.to_tier+", "+x.sla_status_before+"->"+x.sla_status_after+"]":"");
    }).join("\n");
  }catch(e){}
}

async function moveFastLane(fid, runId){
  toast("Requesting SRE-approved Fast Lane for "+fid+" ...");
  var res = await (await fetch("/api/fast-lane",{method:"POST",headers:{"Content-Type":"application/json"},
    body: JSON.stringify({function_id:fid, run_id:runId, approved_by:"sre@bank.com"})})).json();
  if(res.ok){ toast(fid+": "+res.sla_status_before+" -> "+res.sla_status_after+" via "+res.to_tier+" tier"); }
  else { toast("Rejected: "+(res.error||"not eligible")); }
  load();
}

function toast(msg){
  var t=document.getElementById("toast"); t.textContent=msg; t.classList.add("show");
  setTimeout(function(){t.classList.remove("show");}, 3500);
}

load();
setInterval(load, 4000);
</script>
</body>
</html>
"""
