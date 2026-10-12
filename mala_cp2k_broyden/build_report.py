"""Rebuild plots, extracted data and an editable PowerPoint from archived runs.

Run from any directory: python build_report.py
Generates both an editable PowerPoint and a shareable PDF.
Requires numpy, matplotlib, Pillow and python-pptx.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

try:
    import pptx
except ImportError:
    # Temporary dependency installation used on this cluster.
    sys.path.insert(0, '/tmp/mala_report_deps')
    import pptx
from pptx.util import Cm, Pt
from pptx.dml.color import RGBColor

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PLOTS = OUT / 'plots'
PLOTS.mkdir(exist_ok=True)
TEAL, ORANGE, NAVY = '#007F86', '#DE7635', '#152D46'
DOC = 'https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/SCF/MIXING.html'
CASES = [
    dict(key='al298', label='Al · 298 K', atoms=256, cutoff=11000, grid='200³',
         root='logs/mala_cp2k_validation/20260921_225223_562895_2960795',
         mala='cp2k_mala.out', atomic='cp2k_atomic.out', metadata='mala_artifacts.json',
         prep_wall=None, model='Al_298K_0'),
    dict(key='al933', label='Liquid Al · 933 K', atoms=256, cutoff=11000, grid='200³',
         root='933K_hybrid_0/logs/snapshot8_full/20260930_104300_575271_4126053',
         mala='cp2k_external_density.out', atomic='cp2k_atomic_guess.out', metadata='mala_metadata.json',
         prep_wall=697., model='Al_933K_hybrid_0 · snapshot 8'),
    dict(key='b298', label='Boron · 298 K', atoms=144, cutoff=8000, grid='108×108×135',
         root='boron_298K/logs/boron_cp2k/20260922_230542_564624_3335371',
         mala='cp2k_external_density.out', atomic='cp2k_atomic_guess.out',
         metadata='../../boron_validation/20260922_224905_564590_3331209/boron_metadata.json',
         prep_wall=None, model='boron_model_multi_0 · snapshot 6'),
]
ROW = re.compile(r'^\s*(\d+)\s+(\S+/Diag\.)\s+(\S+)\s+([\d.]+)\s+([\d.Ee+-]+)\s+(-?[\d.]+)\s+([\d.Ee+-]+)\s*$', re.M)
HASHES = {}
def record(p):
    HASHES[str(p.resolve().relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()

def parse(p):
    s = p.read_text()
    record(p)
    rows = [dict(iteration=int(i), update=method, alpha=float(alpha), seconds=float(t),
                 convergence=float(c), energy_Ha=float(e), change_Ha=float(de))
            for i, method, alpha, t, c, e, de in ROW.findall(s)]
    n = int(re.search(r'SCF run converged in\s+(\d+) steps', s)[1])
    assert len(rows) == n and [r['iteration'] for r in rows] == list(range(1, n + 1))
    assert 'Mixing method:                            BROYDEN_MIXING' in s
    assert rows[-1]['convergence'] < 1e-5
    elapsed = 0.
    for r in rows:
        elapsed += r['seconds']
        r['cumulative_iteration_seconds'] = elapsed
    return dict(rows=rows, n=n, iteration_time=elapsed,
                final_energy=float(re.search(r'^\s*Total energy:\s+([-\d.]+)', s, re.M)[1]),
                warnings=s.count('WARNING'),
                mpi=int(re.search(r'Total number of message passing processes\s+(\d+)', s)[1]),
                threads=int(re.search(r'Number of threads for this process\s+(\d+)', s)[1]),
                host=re.search(r'PROGRAM STARTED ON\s+(\S+)', s)[1],
                electronic_K=float(re.search(r'Electronic temperature \[K\]:\s+([\d.]+)', s)[1]))

for case in CASES:
    d = ROOT / case['root']
    for route in ['mala', 'atomic']:
        case[route + '_data'] = parse(d / case[route])
        launch = d / ('External-density_launcher.log' if route == 'mala' else 'Atomic-guess_launcher.log')
        record(launch)
        case[route + '_data']['wall'] = float(re.search(r'WALL_SECONDS=([\d.]+)', launch.read_text())[1])
    meta_path = (d / case['metadata']).resolve()
    record(meta_path)
    meta = json.loads(meta_path.read_text())
    timing = meta.get('timings', meta)
    case['stages'] = {k: timing['T_' + k] for k in ['descriptor', 'inference', 'density', 'cube_write']}
    case['prep_components'] = sum(case['stages'].values())
    case['prep'] = case['prep_wall'] or case['prep_components']
    case['prep_basis'] = 'logged complete pipeline wall' if case['prep_wall'] else 'sum of recorded components; lower-bound estimate'
    m, a = case['mala_data'], case['atomic_data']
    assert (m['mpi'], m['threads'], m['host']) == (a['mpi'], a['threads'], a['host'])
    case['scf_wall_saving'] = a['wall'] - m['wall']
    case['end_to_end'] = m['wall'] + case['prep']
    case['energy_difference_meV_atom'] = (m['final_energy'] - a['final_energy']) * 27211.386245988 / case['atoms']
    with (OUT / (case['key'] + '_scf.csv')).open('w') as f:
        fields = ['route'] + list(m['rows'][0])
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        for route in ['mala', 'atomic']:
            writer.writerows(dict(route=route, **r) for r in case[route + '_data']['rows'])

for rel in ['logs/mala_cp2k_validation/20260921_225223_562895_2960795/pipeline.log',
            'logs/mala_cp2k_validation/20260921_225223_562895_2960795/cp2k_mala.inp',
            'logs/mala_cp2k_validation/20260921_225223_562895_2960795/cp2k_atomic.inp',
            '933K_hybrid_0/SNAPSHOT8_RESULTS.md', 'boron_298K/validation_report.txt']:
    record(ROOT / rel)
(OUT / 'source_sha256.json').write_text(json.dumps(HASHES, indent=2))
(OUT / 'results.json').write_text(json.dumps(CASES, indent=2))
with (OUT / 'summary.csv').open('w') as f:
    fields = ['case','cutoff_Ry','atoms','mala_iterations','atomic_iterations','mala_iteration_s','atomic_iteration_s',
              'mala_CP2K_wall_s','atomic_CP2K_wall_s','preparation_s','preparation_basis','mala_total_s','delta_energy_meV_atom']
    w=csv.writer(f); w.writerow(fields)
    for c in CASES:
        m,a=c['mala_data'],c['atomic_data']
        w.writerow([c['label'],c['cutoff'],c['atoms'],m['n'],a['n'],m['iteration_time'],a['iteration_time'],
                    m['wall'],a['wall'],c['prep'],c['prep_basis'],c['end_to_end'],c['energy_difference_meV_atom']])

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                     'axes.labelcolor':NAVY,'text.color':NAVY,'axes.titleweight':'bold','axes.edgecolor':'#BAC4CE',
                     'grid.color':'#E5EBEF','grid.alpha':.85,'figure.facecolor':'white','savefig.facecolor':'white'})
def save(fig,name):
    fig.savefig(PLOTS / (name+'.png'),dpi=200,bbox_inches='tight')
    fig.savefig(PLOTS / (name+'.svg'),bbox_inches='tight')
    fig.savefig(PLOTS / (name+'.pdf'),bbox_inches='tight')
    plt.close(fig)

def trajectories(name, x_kind='iteration', y_kind='energy'):
    fig, axs=plt.subplots(1,3,figsize=(13.4,3.5))
    for ax,c in zip(axs,CASES):
        for route,color,label in [('mala',TEAL,'MALA density → CP2K'),('atomic',ORANGE,'Atomic guess → CP2K')]:
            d=c[route+'_data']; rows=d['rows']
            x=[r['iteration'] if x_kind=='iteration' else r['cumulative_iteration_seconds']/60 for r in rows]
            if y_kind=='energy': y=[r['energy_Ha'] for r in rows]
            elif y_kind=='residual': y=[r['convergence'] for r in rows]
            else:
                y=np.abs(np.array([r['energy_Ha'] for r in rows])-d['final_energy'])*27211.386245988/c['atoms']
                # Rounded table energy cannot resolve the zero endpoint.
                x,y=x[:-1],y[:-1]
            ax.plot(x,y,'o-',ms=3.7,lw=2,color=color,label=label)
        ax.set_title(c['label']+'\n'+str(c['cutoff'])+' Ry',fontsize=12)
        ax.set_xlabel('SCF iteration' if x_kind=='iteration' else 'Cumulative iteration time (min)')
        ax.grid(True,which='major'); ax.ticklabel_format(axis='x',useOffset=False)
        if y_kind=='energy': ax.ticklabel_format(axis='y',useOffset=False,style='plain')
        else:
            ax.set_yscale('log')
            if y_kind=='residual': ax.axhline(1e-5,color=NAVY,ls='--',lw=1)
    axs[0].set_ylabel({'energy':'CP2K SCF total energy (Ha)','residual':'CP2K convergence metric','error':'|Eᵢ − Efinal, own route| (meV/atom)'}[y_kind])
    handles,labels=axs[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,1.06),ncol=2,frameon=False)
    fig.tight_layout(w_pad=2)
    save(fig,name)

trajectories('energy_vs_iteration')
trajectories('energy_vs_time',x_kind='time')
trajectories('residual_vs_iteration',y_kind='residual')
trajectories('energy_distance_vs_time',x_kind='time',y_kind='error')

fig,axs=plt.subplots(1,2,figsize=(13.4,3.7))
labels=[c['label'] for c in CASES]; x=np.arange(3); width=.33
for route,color,label,offset in [('mala',TEAL,'MALA density → CP2K',-width/2),('atomic',ORANGE,'Atomic guess → CP2K',width/2)]:
    vals=[c[route+'_data']['n'] for c in CASES]
    bars=axs[0].bar(x+offset,vals,width,color=color,label=label); axs[0].bar_label(bars,padding=4)
    vals=[c[route+'_data']['wall']/60 for c in CASES]
    bars=axs[1].bar(x+offset,vals,width,color=color); axs[1].bar_label(bars,fmt='%.1f',padding=4)
for ax in axs: ax.set_xticks(x,labels); ax.grid(axis='y'); ax.set_axisbelow(True)
axs[0].set_ylabel('Converged SCF iterations'); axs[0].set_ylim(0,21)
axs[1].set_ylabel('Complete CP2K invocation wall time (min)'); axs[1].set_ylim(0,65)
fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,1.04),ncol=2,frameon=False)
fig.tight_layout(w_pad=3);save(fig,'overview')

fig,axs=plt.subplots(1,3,figsize=(13.4,3.6))
colors=['#8DC9CC','#357DA4','#BBC8D5',TEAL]
for ax,c in zip(axs,CASES):
    ax.barh(1,c['atomic_data']['wall']/60,color=ORANGE)
    left=0.
    vals=[c['stages']['descriptor'],c['stages']['inference'],c['prep']-c['stages']['descriptor']-c['stages']['inference'],c['mala_data']['wall']]
    for v,col,label in zip(vals,colors,['Descriptors','LDOS inference','Density / export / overhead','CP2K with MALA density']):
        ax.barh(0,v/60,left=left/60,color=col,label=label); left+=v
    ax.set_yticks([0,1],['MALA + CP2K','Atomic CP2K']); ax.set_xlabel('Compute time (min)'); ax.grid(axis='x'); ax.set_axisbelow(True)
    ax.set_title(c['label'],fontsize=12)
    for y,val in [(0,left),(1,c['atomic_data']['wall'])]: ax.text(val/60+.5,y,f'{val/60:.1f}',va='center',fontsize=11)
    ax.set_xlim(0,max(left,c['atomic_data']['wall'])*1.17/60)
fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,1.1),ncol=4,frameon=False,fontsize=10)
fig.tight_layout(w_pad=2);save(fig,'time_budget')

fig,axs=plt.subplots(1,2,figsize=(13.4,3.5))
for route,color,label in [('mala',TEAL,'MALA density → CP2K'),('atomic',ORANGE,'Atomic guess → CP2K')]:
    vals=[np.median([r['seconds'] for r in c[route+'_data']['rows'][1:]]) for c in CASES]
    off=-width/2 if route=='mala' else width/2
    bars=axs[0].bar(x+off,vals,width,color=color,label=label);axs[0].bar_label(bars,fmt='%.1f',padding=4)
axs[0].set_ylabel('Median time per step, excluding step 1 (s)');axs[0].set_xticks(x,labels);axs[0].set_ylim(0,240)
vals=[c['energy_difference_meV_atom'] for c in CASES]
bars=axs[1].bar(x,vals,.5,color=TEAL);axs[1].bar_label(bars,fmt='%.4f',padding=4)
axs[1].set_ylabel('Final EMALA − Eatomic (meV/atom)');axs[1].set_xticks(x,labels);axs[1].set_ylim(-.15,.15)
axs[1].axhline(0,color=NAVY,lw=1)
for ax in axs: ax.grid(axis='y');ax.set_axisbelow(True)
fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,1.05),ncol=2,frameon=False)
fig.tight_layout(w_pad=3);save(fig,'step_cost_and_final_energy')

# Structured slide descriptions: editable text, embedded figures and notes.
NS=' '.join(f'xmlns:{k}="{v}"' for k,v in {
 'office':'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
 'style':'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
 'text':'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
 'draw':'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0',
 'fo':'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0',
 'svg':'urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0',
 'presentation':'urn:oasis:names:tc:opendocument:xmlns:presentation:1.0',
 'xlink':'http://www.w3.org/1999/xlink'}.items())
def textbox(x,y,w,h,lines,sty='Body'):
    ps=''.join(f'<text:p text:style-name="{sty}">{escape(t)}</text:p>' for t in lines)
    return f'<draw:frame draw:style-name="Frame" svg:x="{x}cm" svg:y="{y}cm" svg:width="{w}cm" svg:height="{h}cm"><draw:text-box>{ps}</draw:text-box></draw:frame>'
SLIDES=[]
def slide(title,subtitle='',plot=None,body=None,insight=None,small=None,notes=''):
    n=len(SLIDES)+1
    shapes=textbox(1.1,.65,31.4,1.4,[title],'Title')+textbox(1.1,2,31.4,.7,[subtitle],'Subtitle')
    if plot:
        from PIL import Image
        path=PLOTS/(plot+'.png'); iw,ih=Image.open(path).size
        w=31.4; h=w*ih/iw
        shapes+=f'<draw:frame draw:style-name="Frame" svg:x="1.1cm" svg:y="3.2cm" svg:width="{w}cm" svg:height="{h}cm"><draw:image xlink:href="Pictures/{plot}.png" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/></draw:frame>'
    if body: shapes+=textbox(1.35,3.5,30.5,10,body,'Body')
    if insight: shapes+=textbox(1.1,14.2,31.4,1.8,insight,'Insight')
    if small: shapes+=textbox(1.1,16.1,31.4,1.7,small,'Small')
    shapes+=textbox(1.1,18.25,31.4,.5,[f'MALA-assisted CP2K  •  archived single-snapshot comparisons  |  12 October 2026  •  Slide {n:02d}'],'Subtitle')
    if notes: shapes+='<presentation:notes>'+textbox(1,1,25,15,[notes],'Small')+'</presentation:notes>'
    SLIDES.append(f'<draw:page draw:name="Slide {n}" draw:style-name="Page" draw:master-page-name="Default">{shapes}</draw:page>')

slide('Can a MALA density shorten CP2K convergence?',
      'Broyden mixing  •  solid Al, liquid Al and boron  •  measured convergence and compute cost',plot='overview',
      insight=['SCF steps, MALA / atomic: Al 298 K 15 / 17; liquid Al 17 / 17; boron 14 / 16.',
               'MALA and atomic routes both finish with a self-consistent CP2K calculation.'],
      small=['All pairs: 32 MPI ranks × 1 thread. Al cutoff: 11000 Ry; boron cutoff: 8000 Ry.',
             'Numbers on the left are MALA / atomic; wall time on the right includes the complete CP2K invocation.'],
      notes='The comparison is an initializer benchmark: a learned density versus an atomic density guess, both followed by CP2K. Recorded Al counts are 15 versus 17, not the recalled 14 versus 16. Boron is a separate 8000 Ry regime. No statistical uncertainty can be estimated from one pair per case.')
slide('What is compared — and what differs between regimes',
      'Within each pair, the initial density is the intended changed variable.',
      body=['Atomic route: atomic density guess → CP2K diagonalization + Broyden mixing.',
            'MALA route: fresh bispectrum descriptors → predicted LDOS → electron density → CP2K.',
            'Common target: CP2K convergence metric < 10⁻⁵; PBE, DZVP-MOLOPT-SR-GTH, GTH-PBE.',
            'Al 298 K: 256 atoms, model Al_298K_0; electronic smearing 300 K.',
            'Liquid Al: 256 atoms, hybrid model, held-out snapshot 8; actual temperature 931.54 K.',
            'Boron 298 K: 144 atoms, multi model, snapshot 6; compatible grid at 8000 Ry.'],
      insight=['Broyden uses stored SCF history. A better initial density can help, but does not guarantee fewer steps.'],
      small=['Boron’s 11000 Ry probe failed: CP2K grid 120×120×160 versus MALA 108×108×135.',
             'Method reference: CP2K MIXING documentation (full link in README and speaker notes).'],
      notes='Broyden history reference: '+DOC+' . NBUFFER stores previous steps. Al298 archived inputs have subsequently been edited to DIRECT_P_MIXING and cutoff 800; do not interpret them as the original run inputs. Historical output proves Broyden, and pipeline.log records 11000 Ry. The 11000 Ry Al calculations are historical high-grid-cost settings, not a recommendation for production cutoff.')
slide('Energy approaches the converged value along different paths',
      'Directly extracted CP2K SCF table energies; separate energy axis for each material.',plot='energy_vs_iteration',
      insight=['Both Al MALA routes start closer in energy to their final value; boron starts farther away.',
               'Initial energy distance alone does not predict how many SCF steps are needed.'],
      small=['These are CP2K iteration energies, not standalone MALA predictions or physical time trajectories.',
             'The first row follows a diagonalization; mixed SCF energies can overshoot and need not decrease monotonically.'],
      notes='Energy curves cannot compare physical stability across different cells or materials. The first NoMix/Diag row is not the raw input density energy. MALA boron has a much larger first-step energy displacement yet saves two iterations, so energy closeness is not a sufficient convergence predictor.')
slide('Energy versus compute time',
      'Time is the cumulative sum of CP2K’s rounded per-iteration Time column.',plot='energy_vs_time',
      insight=['Al 298 K reaches convergence earlier in this recorded run; liquid Al shows little timing benefit.',
               'Boron’s shorter SCF trace excludes the cost of producing the starting density.'],
      small=['Time starts at the SCF loop; initialization, finalization and MALA preparation are excluded here.',
             'Each point is the energy at the end of its iteration. Accuracy of summed time is limited by 0.1 s rounding.'],
      notes='Summed iteration seconds MALA/atomic: Al298 2158.7/3157.8; liquid Al 2370.3/2291.7; B 472.5/543.0. Complete invocation times are larger. These traces are not end-to-end speed measurements.')
slide('The SCF convergence metric determines the stopping point',
      'Dashed line: EPS_SCF = 10⁻⁵ for every comparison.',plot='residual_vs_iteration',
      insight=['The late SCF tail matters: both liquid-Al routes cross the threshold at step 17.',
               'Short-term oscillations are visible even when the final calculation converges.'],
      small=['“Convergence” is the metric printed by CP2K; it is not an energy error or a measured density RMSE.',
             'Broyden history changes the path after initialization; these three pairs do not isolate a temperature effect.'],
      notes='Differences in geometry, model, material and smearing accompany the change in regime. The data support a case-specific benefit, not a claim that temperature alone causes the difference. No ablation of mixing parameters was performed in this report.')
slide('Does the SCF saving pay for MALA preparation?',
      'Complete CP2K wall time plus preparation; queue delays and failed probes are excluded.',plot='time_budget',
      insight=['Al 298 K: ≈13.3% less total compute time. Liquid Al: 32.0% more.',
               'Boron: at least 70.2% more; descriptor generation dominates the preparation cost.'],
      small=['Al 298 K prep ≈558.6 s and boron ≈484.2 s: sums of recorded components, lower-bound estimates.',
             'Liquid Al prep = 697 s logged pipeline wall. Al 298 K’s earlier report omitted cube writing from its total.'],
      notes='Break-even requires preparation time < saved complete CP2K wall time. Savings: Al298 995.38 s, liquid Al -74.80 s, boron 76.16 s. Component sum Al298 includes descriptor, inference, density and cube serialization: 558.645374 s. Boron 484.234379 s. Component sums omit unrecorded overhead; Al298 overall saving is an estimate and boron slowdown is a lower bound. Liquid Al uses logged complete pipeline wall including overhead. Preparation and CP2K can run on different workers, so the total is sequential compute wall, not a uniform-hardware benchmark or allocation cost.')
slide('Why step count and runtime tell different stories',
      'Per-step timing varies; finite SCF tolerance also leaves small final-energy differences.',plot='step_cost_and_final_energy',
      insight=['Al 298 K’s ≈30.3% CP2K wall saving is larger than its 11.8% iteration saving.',
               'Final-energy differences: |ΔE| < 0.12 meV/atom. Tighter SCF convergence remains to be checked.'],
      small=['Median step time excludes the distinct first NoMix step. Run-to-run performance variability remains unmeasured.',
             'Liquid Al emits “smearing includes the last MO” warnings: additional unoccupied orbitals need checking.'],
      notes='Final external-minus-atomic energy differences in meV/atom: Al298 ~0.07860, liquid Al ~0.03251, B ~−0.11758. Small differences are consistent with finite SCF accuracy but tighter convergence is required to establish that explanation. The Al298 cube integrated to 768.2867545890 electrons versus target 768; final SCF is ~768 electrons. This is an additional initializer difference, not evidence of a physical charge effect. The large Al298 step-time difference is observed, but its cause cannot be established from one pair; do not claim the learned density inherently makes each iteration faster.')
slide('What these runs support',
      'Three case studies; a useful initializer benefit is conditional on total cost.',
      body=['Al 298 K: the recorded MALA route saves two SCF steps and appears faster after preparation.',
            'Liquid Al: equal iteration count; preparation adds cost with no SCF acceleration.',
            'Boron: two fewer steps, but ~76 s saved cannot recover ~484 s of preparation.',
            'Next: repeat matched pairs on the same hardware and several held-out snapshots.',
            'Then: tighten EPS_SCF, check added MOs, and audit density normalization.',
            'Benchmark validated production grids separately; report preparation and CP2K costs together.'],
      insight=['The decision criterion is simple: saved CP2K time must exceed density-preparation time.'],
      small=['Do not generalize these timings to a temperature trend or an average speedup.',
             'Models, structures, cutoffs and workers differ between regimes; only within-pair comparisons are shown.'],
      notes='The positive Al298 end-to-end result is approximate because only component preparation timings exist and per-step timings vary strongly between routes. Boron is necessarily slower for a fresh prediction under these recorded timings. Reusing already computed densities changes the accounting and must be labeled separately.')
slide('Appendix · late energy convergence on a logarithmic scale',
      'Each route is referenced to its own final printed CP2K total energy.',plot='energy_distance_vs_time',
      insight=['This view exposes the late convergence tail hidden by the full energy scale.'],
      small=['Endpoints are omitted because rounded table values cannot resolve the zero energy difference.',
             'This is distance to the run’s endpoint, not error against an independently converged DFT reference.'],
      notes='The own-route reference removes finite differences between endpoints to show how each energy settles. This quantity must not be described as an ML prediction error or an independent accuracy assessment.')
slide('Appendix · exact run selection and provenance',
      'Raw traces, numerical summaries and SHA-256 hashes accompany this deck.',
      body=['Al 298 K: job 562895 · 21 September 2026 · gh003 · fresh MALA descriptors and LDOS.',
            'Liquid Al: snapshot 8 · CP2K job 575329 · 30 September 2026 · cge065.',
            'Boron: snapshot 6 · CP2K job 564624 · 22 September 2026 · gh003.',
            'Excluded: liquid snapshot 7 precomputed-density run (23 vs 17 steps).',
            'Excluded: DIRECT_P_MIXING, resampled-grid, failed and incomplete experiments.',
            'Reproducibility: build_report.py, results.json, summary.csv, per-step CSVs and source_sha256.json.'],
      insight=['Historical Al 298 K input files were edited after execution; use output and pipeline evidence.'],
      small=['Full workspace-relative paths, timing definitions and method reference are in the companion README.',
             'No new simulation was run; every plotted point comes from the selected archived CP2K output.'],
      notes='Al298: '+CASES[0]['root']+'; Liquid Al: '+CASES[1]['root']+'; Boron: '+CASES[2]['root']+'. The fresh external snapshot7 continuation also has 17 steps but is not mixed with its earlier atomic reference; the matched fresh snapshot8 pair is used consistently.')

images=sorted(PLOTS.glob('*.png'))
pres = pptx.Presentation()
pres.slide_width, pres.slide_height = Cm(33.867), Cm(19.05)
pres.core_properties.title = 'MALA-assisted CP2K: Broyden convergence and compute cost'
pres.core_properties.subject = 'Archived single-snapshot comparisons for Al and boron'
pres.core_properties.author = 'Simulation analysis'
nsmap = dict(re.findall(r'xmlns:(\w+)="([^"]+)"', NS))
styles_map = {'Title':(24,NAVY,True), 'Subtitle':(12,'#526575',False),
              'Body':(18,NAVY,False), 'Small':(12,'#526575',False), 'Insight':(15,TEAL,True)}
for description in SLIDES:
    page = ET.fromstring('<wrapper '+NS+'>'+description+'</wrapper>')[0]
    page_slide = pres.slides.add_slide(pres.slide_layouts[6])
    for frame in page.findall('draw:frame', nsmap):
        dims = [Cm(float(frame.get('{'+nsmap['svg']+'}'+attr).removesuffix('cm'))) for attr in ['x','y','width','height']]
        img = frame.find('draw:image',nsmap)
        if img is not None:
            filename = Path(img.get('{'+nsmap['xlink']+'}href')).name
            page_slide.shapes.add_picture(str(PLOTS/filename),*dims)
            continue
        box = page_slide.shapes.add_textbox(*dims)
        tf = box.text_frame
        tf.clear(); tf.word_wrap=True
        tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0
        for i,para in enumerate(frame.findall('draw:text-box/text:p',nsmap)):
            pp=tf.paragraphs[0] if i==0 else tf.add_paragraph()
            name=para.get('{'+nsmap['text']+'}style-name')
            size,color,bold=styles_map[name]
            pp.text=''.join(para.itertext())
            pp.font.name='DejaVu Sans'; pp.font.size=Pt(size); pp.font.bold=bold
            pp.font.color.rgb=RGBColor.from_string(color[1:])
            pp.space_after=Pt(11 if name=='Body' else 4)
            pp.line_spacing=1.13 if name=='Body' else 1.05
    notes = page.find('presentation:notes',nsmap)
    if notes is not None:
        page_slide.notes_slide.notes_text_frame.text=' '.join(notes.itertext())
pres.save(OUT/'mala_cp2k_broyden.pptx')
# Render the same slide descriptions directly to PDF. This keeps rebuilding
# independent of a LibreOffice installation with the Impress import filters.
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
from PIL import Image
notes_text=[]
with PdfPages(OUT/'mala_cp2k_broyden.pdf') as pdf:
    for number,description in enumerate(SLIDES,1):
        page=ET.fromstring('<wrapper '+NS+'>'+description+'</wrapper>')[0]
        fig=plt.figure(figsize=(33.867/2.54,19.05/2.54))
        fig.canvas.draw()
        renderer=fig.canvas.get_renderer()
        for frame in page.findall('draw:frame',nsmap):
            xx,yy,ww,hh=[float(frame.get('{'+nsmap['svg']+'}'+attr).removesuffix('cm')) for attr in ['x','y','width','height']]
            img=frame.find('draw:image',nsmap)
            if img is not None:
                ax=fig.add_axes([xx/33.867,1-(yy+hh)/19.05,ww/33.867,hh/19.05])
                ax.imshow(Image.open(PLOTS/Path(img.get('{'+nsmap['xlink']+'}href')).name));ax.axis('off')
                continue
            current_y=yy
            for para in frame.findall('draw:text-box/text:p',nsmap):
                name=para.get('{'+nsmap['text']+'}style-name')
                size,color,bold=styles_map[name]
                fp=FontProperties(family='DejaVu Sans',size=size,weight='bold' if bold else 'normal')
                width_px=ww/2.54*fig.dpi
                words=''.join(para.itertext()).split(); lines=[];line=''
                for word in words:
                    candidate=(line+' '+word).strip()
                    if line and renderer.get_text_width_height_descent(candidate,fp,False)[0]>width_px:
                        lines.append(line);line=word
                    else:line=candidate
                if line:lines.append(line)
                spacing=size*(1.13 if name=='Body' else 1.05)*2.54/72
                for line in lines:
                    fig.text(xx/33.867,1-current_y/19.05,line,fontproperties=fp,color=color,va='top')
                    current_y+=spacing
                current_y+=(11 if name=='Body' else 4)*2.54/72
            assert current_y<=yy+hh+.25, f'Text overflow on slide {number}: {current_y} > {yy+hh}'
        pdf.savefig(fig)
        fig.savefig(OUT/f'slide_{number:02d}.png',dpi=90)
        plt.close(fig)
        notes=page.find('presentation:notes',nsmap)
        notes_text.append(f'Slide {number}\n'+(' '.join(notes.itertext()) if notes is not None else '')+'\n')
(OUT/'speaker_notes.txt').write_text('\n'.join(notes_text))
print('Built',len(SLIDES),'slides and',len(images),'figures.')
for c in CASES:
    print(c['label'],c['mala_data']['n'],c['atomic_data']['n'],f"total={c['end_to_end']:.2f}s vs {c['atomic_data']['wall']:.2f}s; prep={c['prep']:.2f}s")
