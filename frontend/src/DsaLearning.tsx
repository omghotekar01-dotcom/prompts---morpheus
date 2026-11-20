import { BookOpen, Braces, Code2, Database, Network, Search } from 'lucide-react'
import './dsa-learning.css'

type DsaLearningProps = {
  onNavigate: (destination: string) => void
}

const structures = [
  {
    name: 'Robin Hood hash index',
    family: 'Exact-key lookup',
    icon: Search,
    idea: 'Stores keys in an open-addressed hash table. When two keys collide, a key that has travelled farther can take a nearer slot, helping keep probe lengths more balanced.',
    tradeoff: 'Expected fast exact lookups; collisions and resizing affect the actual cost. It is not ordered, so it is not the choice for sorted range scans.',
    complexity: 'Expected lookup: O(1); worst case: O(n)',
    source: 'core/include/morpheus/structures.hpp'
  },
  {
    name: 'B+ tree',
    family: 'Ordered index',
    icon: Braces,
    idea: 'Keeps keys in sorted leaves connected by a balanced multiway tree. Internal nodes guide searches; leaf links support ordered traversal.',
    tradeoff: 'Supports exact and range access while remaining balanced. Nodes, splits, and pointer traversal add overhead compared with a compact array.',
    complexity: 'Lookup: O(log n); range: O(log n + k)',
    source: 'core/include/morpheus/bplus_tree.hpp'
  },
  {
    name: 'Sorted array index',
    family: 'Ordered lookup',
    icon: Database,
    idea: 'Stores key-value rows in sorted order and uses binary search to find the start of a range.',
    tradeoff: 'Compact and effective for reads and ranges. Inserting or erasing a row can shift many elements.',
    complexity: 'Lookup: O(log n); insert/erase: O(n)',
    source: 'core/include/morpheus/mutable_indices.hpp'
  },
  {
    name: 'Mutable prefix trie',
    family: 'Prefix search',
    icon: Search,
    idea: 'Walks one character at a time through a tree of string prefixes. A prefix query reaches the matching subtree before collecting its values.',
    tradeoff: 'Work depends on key length and matching output, not a binary search over all rows. Per-character nodes can use more memory.',
    complexity: 'Prefix walk: O(L), plus returned matches',
    source: 'core/include/morpheus/mutable_indices.hpp'
  },
  {
    name: 'Compressed bitmap',
    family: 'Set filtering',
    icon: Database,
    idea: 'Represents matching record IDs as a set and combines sets with operations such as intersection and union.',
    tradeoff: 'Useful for combining categorical filters. Storage and operation cost depend on the IDs and their distribution.',
    complexity: 'Cost depends on encoded set size',
    source: 'core/include/morpheus/compressed_bitmap.hpp'
  },
  {
    name: 'CSR graph',
    family: 'Graph traversal',
    icon: Network,
    idea: 'Compressed Sparse Row stores adjacency lists in contiguous offset and neighbor arrays for read-oriented graph access.',
    tradeoff: 'Compact traversal over a built graph. Changing edges requires rebuilding the structure.',
    complexity: 'Traversal: O(V + E)',
    source: 'core/include/morpheus/csr_graph.hpp'
  }
]

export default function DsaLearning({ onNavigate }: DsaLearningProps) {
  return <div className="functional-page dsa-learning-page">
    <header className="dsa-learning-heading">
      <div className="page-head-icon"><BookOpen size={23}/></div>
      <div>
        <span className="section-kicker">LEARN DSA</span>
        <h2>Data structures, with real trade-offs</h2>
        <p>See how each structure fits an access pattern, what it costs, and where MORPHEUS implements it.</p>
      </div>
    </header>

    <section className="dsa-learning-intro">
      <div>
        <span className="section-kicker">THE CORE IDEA</span>
        <h3>Choose for the operations, not just the data.</h3>
        <p>A hash index favors exact lookup; an ordered index can answer ranges; a trie follows prefixes. MORPHEUS models workload routes and constraints to compare candidates. The displayed score is a model result, not a benchmark.</p>
      </div>
      <div className="dsa-learning-actions">
        <button className="primary-button" onClick={() => onNavigate('Workloads')}><Braces size={18}/> Try a workload</button>
        <button className="secondary-button" onClick={() => onNavigate('Code Generator')}><Code2 size={18}/> Open Code & Verify</button>
      </div>
    </section>

    <section className="dsa-structure-grid" aria-label="Implemented data structures">
      {structures.map(({ name, family, icon: Icon, idea, tradeoff, complexity, source }) => <article className="panel dsa-structure-card" key={name}>
        <div className="dsa-structure-top">
          <span className="dsa-structure-icon"><Icon size={19}/></span>
          <span className="dsa-structure-family">{family}</span>
        </div>
        <h3>{name}</h3>
        <p>{idea}</p>
        <div className="dsa-tradeoff"><strong>Trade-off</strong><span>{tradeoff}</span></div>
        <div className="dsa-complexity"><strong>Complexity intuition</strong><span>{complexity}</span></div>
        <code className="dsa-source">{source}</code>
      </article>)}
    </section>

    <section className="dsa-language-grid" aria-label="MORPHEUS language roles">
      <article className="panel dsa-language-card">
        <span className="section-kicker">PRODUCTION ENGINE</span>
        <h3>C++20</h3>
        <p>The native optimizer and physical data structures run the search and profiling work. This is the main DSA implementation layer.</p>
      </article>
      <article className="panel dsa-language-card">
        <span className="section-kicker">SCORING</span>
        <h3>Java 17+</h3>
        <p>The deterministic scorer checks candidate constraints and calculates a weighted score from supplied modeled metrics. It is not a trained machine-learning model or a benchmark.</p>
      </article>
      <article className="panel dsa-language-card">
        <span className="section-kicker">ALGORITHM LESSON</span>
        <h3>C11 binary search</h3>
        <p>The separate C lesson searches a validated ascending array in O(log n) comparisons and O(1) extra space. The sorted-input requirement is part of the algorithm's contract.</p>
        <code className="dsa-source">core/src/binary_search.c</code>
      </article>
    </section>

    <aside className="dsa-learning-note">
      <Network size={19}/>
      <p><strong>How to read complexity:</strong> <code>n</code> is the number of records, <code>L</code> is a key's length, <code>k</code> is the number of returned results, and <code>V</code>/<code>E</code> are graph vertices/edges. These are standard algorithmic intuitions; actual time and memory depend on data and machine.</p>
    </aside>
  </div>
}
