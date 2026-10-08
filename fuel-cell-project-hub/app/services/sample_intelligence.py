"""Evidence-based, logical sample and image relationships. Never writes source files."""

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from app.services.storage import timestamp

RULE_VERSION = '2'
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.gif', '.webp'}
# Ordered, centrally seeded categories; users may add or deactivate records.
SUBTYPES = (
    ('Overlay', r'overlay'), ('Pore Map', r'(?:all[ _-]*)?pore[ _-]*map'),
    ('Outline', r'(?:numbered[ _-]*)?outlines?|drawing of'),
    ('Binary / Threshold', r'binary|threshold'), ('Mask', r'mask'),
    ('Segmentation', r'segment(?:ed|ation)?'), ('Annotated', r'annotated|labelled'),
    ('Fiber Map', r'fiber[ _-]*map'), ('Pore Identification', r'pore[ _-]*ident'),
    ('Filtered', r'filtered|median'), ('Composite', r'composite'),
    ('Comparison', r'comparison'), ('Processed', r'processed|heat[ _-]*map|contrast'),
)


def normalize(value):
    return re.sub(r'[^a-z0-9%]+', '', str(value).casefold())


def create_schema(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS sample_aliases(sample_id TEXT,alias TEXT,normalized_alias TEXT,
      source TEXT,confidence TEXT,manually_confirmed INTEGER DEFAULT 0,
      PRIMARY KEY(sample_id,normalized_alias));
    CREATE TABLE IF NOT EXISTS file_sample_links(file_id TEXT,sample_id TEXT,relationship_type TEXT,
      confidence TEXT,source TEXT,manually_confirmed INTEGER DEFAULT 0,explanation TEXT,
      PRIMARY KEY(file_id,sample_id));
    CREATE INDEX IF NOT EXISTS sample_files ON file_sample_links(sample_id,file_id);
    CREATE TABLE IF NOT EXISTS sample_decisions(file_id TEXT PRIMARY KEY,mode TEXT);
    CREATE TABLE IF NOT EXISTS classification_cache(file_id TEXT PRIMARY KEY,signature TEXT);
    CREATE TABLE IF NOT EXISTS asset_categories(id TEXT PRIMARY KEY,name TEXT UNIQUE,parent_id TEXT,
      applicable_file_type TEXT,active INTEGER DEFAULT 1,sort_order INTEGER);
    CREATE TABLE IF NOT EXISTS image_assets(file_id TEXT PRIMARY KEY,image_category TEXT,
      image_subcategory TEXT,base_key TEXT,family_id TEXT,original_id TEXT,confidence TEXT,
      explanation TEXT,manual INTEGER DEFAULT 0,signature TEXT,rules_version TEXT);
    CREATE INDEX IF NOT EXISTS image_family ON image_assets(family_id,file_id);
    CREATE TABLE IF NOT EXISTS image_families(id TEXT PRIMARY KEY,original_id TEXT,status TEXT);
    CREATE TABLE IF NOT EXISTS image_relationships(parent_image_id TEXT,child_image_id TEXT,
      relationship_type TEXT,source TEXT,PRIMARY KEY(parent_image_id,child_image_id));
    ''')
    categories = [('original', 'Original', ''), ('generated', 'Generated / Processed', ''),
                  ('reference', 'Reference', ''), ('unknown', 'Unknown', '')]
    categories += [(normalize(n), n, 'generated') for n, _ in SUBTYPES]
    for i, (identity, name, parent) in enumerate(categories):
        db.execute('INSERT OR IGNORE INTO asset_categories VALUES (?,?,?,?,?,?)',
                   (identity, name, parent, 'Image', 1, i))
    db.execute('''INSERT OR IGNORE INTO file_sample_links
      SELECT l.file_id,l.sample_id,'primary','HIGH','manual',1,'Existing confirmed relationship'
      FROM research_file_links l JOIN research_objects o ON o.id=l.sample_id
      WHERE l.sample_id<>'' AND o.kind='sample' ''')
    db.execute('CREATE INDEX IF NOT EXISTS confirmed_sample_files ON research_file_links(sample_id,file_id)')


def classify_image(name, parent=''):
    stem = PurePosixPath(name).stem
    context = stem.casefold()
    matches = [(n, re.search(pattern, context)) for n, pattern in SUBTYPES]
    subtype, match = next(((n, m) for n, m in matches if m), ('', None))
    explicit_original = re.search(r'(?:^|[_ -])original(?:$|[_ -])', context)
    generated_folder = re.search(r'(?:segmented|processed|generated) images', parent.casefold())
    if explicit_original:
        category, subtype, confidence, why = 'Original', '', 'HIGH', 'Explicit source image marker within this processing family'
    elif subtype:
        category, confidence, why = 'Generated / Processed', 'HIGH', 'Filename processing marker: ' + match.group()
    elif generated_folder:
        category, subtype, confidence, why = 'Generated / Processed', 'Processed', 'MEDIUM', 'Processing folder'
    elif re.search(r'reference|presentation|logo|icon', parent.casefold()):
        category, confidence, why = 'Reference', 'MEDIUM', 'Reference/presentation folder'
    elif PurePosixPath(name).suffix.casefold() in ('.tif', '.tiff'):
        category, confidence, why = 'Original', 'MEDIUM', 'TIFF without processing marker; reviewable source candidate'
    else:
        category, confidence, why = 'Unknown', 'LOW', 'No reliable image purpose marker'
    base = re.sub(r'^drawing of[ _-]*', '', stem, flags=re.I)
    base = re.split(r'[_ -](?:original|all[_ -]*pore|pore[_ -]*map|numbered[_ -]*outline|outline|overlay|mask|binary|threshold|segment|processed|scaled|median|contrast|batch\d|r\d+[_ -]t\d)', base, maxsplit=1, flags=re.I)[0]
    return category, subtype, normalize(base), confidence, why


class SampleIntelligence:
    def __init__(self, catalog):
        self.catalog = catalog
        self.project = catalog.locations.value['active']['id']
        self._aliases = None
        self._alias_signature = ''

    def discover(self, db):
        """Only repeated, qualified specimen naming creates new objects."""
        candidates = defaultdict(Counter)
        for source, origin, name, parent in db.execute(
                'SELECT source_id,data_origin,name,parent_folder FROM file_metadata'):
            context = name + '/' + parent
            if re.search(r'holy(?:[ _-]*gdl|middle|top|bottom|[ _-])', context, re.I):
                candidates[(source, origin, 'Holy GDL')]['Holy'] += 1
                if re.search('holygdl', normalize(context)):
                    candidates[(source, origin, 'Holy GDL')]['HolyGDL'] += 1
            for m in re.finditer(r'(?<!\d)(\d{3,5})[ _-]*Pa(?:scal)?(?![a-z])', context, re.I):
                display = m.group(1) + ' Pascal'
                candidates[(source, origin, display)][m.group()] += 1
            for m in re.finditer(r'(?<!\d)(\d{1,3})%[ _-]*(\d+)[ _-]*Pass(?:es)?', context, re.I):
                candidates[(source, origin, f'{m.group(1)}% {m.group(2)} Pass')][m.group()] += 1
        existing = {(o, normalize(json.loads(p)['name'])): identity for identity, o, p in db.execute(
            "SELECT id,origin,payload FROM research_objects WHERE project_id=? AND kind='sample'", (self.project,))}
        for (source, origin, name), aliases in candidates.items():
            if origin not in ('current', 'legacy') or sum(aliases.values()) < 3:
                continue
            key = origin, normalize(name)
            identity = existing.get(key) or 'S-' + hashlib.sha256((self.project + origin + name).encode()).hexdigest()[:12]
            if key not in existing:
                now = timestamp()
                payload = dict(id=identity, name=name, normalized_name=normalize(name), description='Discovered from repeated qualified file/folder names',
                               status='Needs review', created_date='', notes='', aliases=list(aliases))
                db.execute('INSERT INTO research_objects VALUES (?,?,?,?,?,?,0)',
                           (identity, 'sample', self.project, origin, json.dumps(payload), now))
                existing[key] = identity
            for alias in (name, *aliases):
                db.execute('INSERT OR IGNORE INTO sample_aliases VALUES (?,?,?,?,?,0)',
                           (identity, alias, normalize(alias), 'repeated_naming', 'HIGH'))
        self._aliases = None

    def aliases(self, db):
        if self._aliases is None:
            self._aliases = list(db.execute('''SELECT a.sample_id,a.alias,a.normalized_alias,o.origin
              FROM sample_aliases a JOIN research_objects o ON o.id=a.sample_id
              WHERE o.project_id=?''', (self.project,)))
            self._alias_signature = hashlib.sha256(json.dumps(self._aliases,sort_keys=True).encode()).hexdigest()
        return self._aliases

    def apply(self, db, row, force=False):
        identity = row['id']
        aliases=self.aliases(db)
        sample_signature=json.dumps([row['relative_path'],row.get('signature'),self._alias_signature,RULE_VERSION])
        cache=db.execute('SELECT signature FROM classification_cache WHERE file_id=?',(identity,)).fetchone()
        samples_changed=force or not cache or cache[0]!=sample_signature
        decision = db.execute('SELECT mode FROM sample_decisions WHERE file_id=?', (identity,)).fetchone()
        manual = db.execute('SELECT payload FROM overrides WHERE id=?', (identity,)).fetchone()
        manual_values = json.loads(manual[0]) if manual else {}
        if samples_changed and not decision and 'sample_id' not in manual_values:
            db.execute('DELETE FROM file_sample_links WHERE file_id=? AND manually_confirmed=0', (identity,))
            found = {}
            filename, folder = normalize(row['name']), normalize(row['parent_folder'])
            for sample, alias, norm, origin in aliases:
                if origin != row['data_origin']:
                    continue
                # Numeric fragments are never unqualified aliases.
                if norm.isdigit() or len(norm) < 4:
                    continue
                name_match = norm in filename
                if norm == 'holy':
                    name_match = bool(re.search(r'(?:^|\d)holy(?:gdl|middle|top|bottom|\d)', filename)) or bool(re.search(r'(?<![a-z])holy(?:[_ -]|$)', row['name'], re.I))
                folder_match = norm in folder
                if name_match or folder_match:
                    strength = 2 if name_match else 1
                    old = found.get(sample)
                    if not old or strength > old[0]:
                        found[sample] = (strength, alias)
                if norm=='1344pascal' and re.search(r'(?:^|/)Pascal(?: 4-8)?(?:/|$)',row['parent_folder'],re.I):
                    found.setdefault(sample,(1,'Pascal folder with observed 1344Pa images'))
            # Clear filename identification wins over conflicting folders.
            best = max((v[0] for v in found.values()), default=0)
            for sample, (strength, alias) in found.items():
                if strength < best:
                    continue
                db.execute('INSERT OR IGNORE INTO file_sample_links VALUES (?,?,?,?,?,0,?)',
                           (identity, sample, 'primary' if len(found) == 1 else 'contains',
                            'HIGH' if strength == 2 else 'MEDIUM', 'filename' if strength == 2 else 'folder_context',
                            f'Alias "{alias}" in ' + ('filename' if strength == 2 else 'folder')))
        elif samples_changed and 'sample_id' in manual_values and not decision:
            db.execute('DELETE FROM file_sample_links WHERE file_id=?', (identity,))
            if manual_values['sample_id']:
                db.execute('INSERT OR REPLACE INTO file_sample_links VALUES (?,?,?,?,?,1,?)',
                           (identity, manual_values['sample_id'], 'primary', 'HIGH', 'manual', 'Explicit primary assignment'))
        if samples_changed:
            db.execute('INSERT OR REPLACE INTO classification_cache VALUES (?,?)',(identity,sample_signature))
        if row['extension'] not in IMAGE_EXTENSIONS:
            return
        signature = json.dumps([row.get('signature'), row['relative_path'], RULE_VERSION])
        cached = db.execute('SELECT signature,manual FROM image_assets WHERE file_id=?', (identity,)).fetchone()
        if cached and (cached[1] or cached[0] == signature and not force):
            return
        category, subtype, base, confidence, why = classify_image(row['name'], row['parent_folder'])
        db.execute('''INSERT INTO image_assets VALUES (?,?,?,?,?,?,?,?,0,?,?) ON CONFLICT(file_id) DO UPDATE SET
          image_category=excluded.image_category,image_subcategory=excluded.image_subcategory,base_key=excluded.base_key,
          confidence=excluded.confidence,explanation=excluded.explanation,signature=excluded.signature,rules_version=excluded.rules_version''',
                   (identity, category, subtype, base, '', '', confidence, why, signature, RULE_VERSION))

    def reconcile(self, cancel=None, progress=None):
        with self.catalog.connect() as db:
            self.discover(db)
            cursor = db.execute('SELECT payload FROM files')
            count = 0
            while batch := cursor.fetchmany(250):
                if cancel and cancel():
                    from app.services.project_storage import IndexCancelled
                    raise IndexCancelled('Classification cancelled; completed batches preserved.')
                for (payload,) in batch:
                    row = json.loads(payload)
                    self.apply(db, row)
                    count += 1
                db.commit()
                if progress:
                    progress(count)
            self.families(db)
            summary = self.summary(db)
        self.catalog.log('sample_intelligence', files_scanned=count, **summary)
        return dict(files_scanned=count, **summary)

    def families(self, db):
        groups = defaultdict(list)
        for identity, base, category, source, origin, parent, name in db.execute('''SELECT a.file_id,a.base_key,a.image_category,
          m.source_id,m.data_origin,m.parent_folder,m.name FROM image_assets a JOIN file_metadata m ON m.id=a.file_id WHERE a.manual=0'''):
            # Scope acquisition/run tree; stem is required as well as folder context.
            scope = re.sub(r'/(?:images|originals?|processed|generated|overlays?|outlines?)$', '', parent, flags=re.I)
            groups[(source, origin, scope, base)].append((identity, category, name))
        db.execute("DELETE FROM image_relationships WHERE source='automatic'")
        for key, entries in groups.items():
            family = 'IF-' + hashlib.sha256(json.dumps(key).encode()).hexdigest()[:20]
            originals = [identity for identity, cat, name in entries if cat == 'Original']
            explicit = [identity for identity,cat,name in entries if cat=='Original' and re.search(r'[_ -]original\.',name,re.I)]
            if len(explicit)==1:
                originals=explicit
            elif explicit:
                variants=[(identity,name) for identity,cat,name in entries if identity in explicit]
                if len({PurePosixPath(name).stem.casefold() for _,name in variants})==1:
                    originals=[min(variants,key=lambda r:(PurePosixPath(r[1]).suffix.casefold() not in ('.tif','.tiff'),r[0]))[0]]
            original = originals[0] if len(originals) == 1 else ''
            status = 'Original located' if original else 'Ambiguous originals' if originals else 'Original Not Located'
            db.execute('INSERT OR REPLACE INTO image_families VALUES (?,?,?)', (family, original, status))
            for identity, category, name in entries:
                db.execute('UPDATE image_assets SET family_id=?,original_id=? WHERE file_id=? AND manual=0', (family, original, identity))
                if original and identity != original and category == 'Generated / Processed':
                    db.execute('INSERT OR IGNORE INTO image_relationships VALUES (?,?,?,?)', (original, identity, 'derived_from', 'automatic'))

    def related_samples(self, identity):
        with self.catalog.connect() as db:
            return [dict(id=i, name=json.loads(p)['name'], confidence=c, source=s, explanation=e, relationship_type=r, manually_confirmed=bool(m))
                    for i,p,c,s,e,r,m in db.execute('''SELECT l.sample_id,o.payload,l.confidence,l.source,l.explanation,l.relationship_type,l.manually_confirmed
                      FROM file_sample_links l JOIN research_objects o ON o.id=l.sample_id WHERE l.file_id=? ORDER BY l.manually_confirmed DESC''', (identity,))]

    def assign(self, file_id, sample_ids, relationship='primary'):
        if relationship not in ('primary','contains','compares','derived_from','references'):
            raise ValueError('Choose a supported relationship.')
        with self.catalog.connect() as db:
            row = db.execute('SELECT data_origin FROM file_metadata WHERE id=?', (file_id,)).fetchone()
            if not row:
                raise ValueError('Choose an indexed file.')
            for identity in sample_ids:
                if not db.execute("SELECT 1 FROM research_objects WHERE id=? AND kind='sample' AND project_id=? AND origin=?",
                                  (identity, self.project, row[0])).fetchone():
                    raise ValueError('Choose samples from this project and origin.')
            db.execute('INSERT OR REPLACE INTO sample_decisions VALUES (?,?)', (file_id, 'manual'))
            db.execute('DELETE FROM file_sample_links WHERE file_id=?', (file_id,))
            for identity in sample_ids:
                db.execute('INSERT INTO file_sample_links VALUES (?,?,?,?,?,1,?)',
                           (file_id, identity, relationship, 'HIGH', 'manual', 'User confirmed sample relationship'))

    def edit_image(self, file_id, category, subtype='', original_id=''):
        with self.catalog.connect() as db:
            valid = {n for (n,) in db.execute('SELECT name FROM asset_categories WHERE active=1')}
            if category not in valid or subtype and subtype not in valid:
                raise ValueError('Choose an active image category.')
            if original_id:
                if file_id == original_id or not db.execute('''SELECT 1 FROM image_assets a JOIN file_metadata m ON m.id=a.file_id
                  JOIN file_metadata c ON c.id=? WHERE a.file_id=? AND m.source_id=c.source_id AND m.data_origin=c.data_origin''', (file_id,original_id)).fetchone():
                    raise ValueError('Choose a different original from the same source.')
            original_family = db.execute('SELECT family_id FROM image_assets WHERE file_id=?',(original_id,)).fetchone() if original_id else None
            family = original_family[0] if original_family and original_family[0] else 'IF-manual-' + (original_id or file_id)
            db.execute('DELETE FROM image_relationships WHERE child_image_id=?',(file_id,))
            db.execute('UPDATE image_assets SET image_category=?,image_subcategory=?,family_id=?,original_id=?,manual=1,confidence=?,explanation=? WHERE file_id=?',
                       (category, subtype, family, original_id, 'HIGH', 'Manual image classification', file_id))
            if original_id:
                db.execute('UPDATE image_assets SET manual=1 WHERE family_id=?',(family,))
                db.execute('UPDATE image_assets SET family_id=?,original_id=?,manual=1 WHERE file_id=?', (family, original_id, original_id))
                db.execute('INSERT OR REPLACE INTO image_families VALUES (?,?,?)', (family,original_id,'Original located'))
                db.execute('INSERT OR REPLACE INTO image_relationships VALUES (?,?,?,?)', (original_id,file_id,'derived_from','manual'))

    def reset(self, file_id):
        with self.catalog.connect() as db:
            row=db.execute('SELECT payload FROM files WHERE id=?',(file_id,)).fetchone()
            if not row:raise ValueError('Choose an indexed file.')
            db.execute('DELETE FROM sample_decisions WHERE file_id=?',(file_id,))
            db.execute('DELETE FROM file_sample_links WHERE file_id=?',(file_id,))
            db.execute('DELETE FROM research_file_links WHERE file_id=?',(file_id,))
            override=db.execute('SELECT payload FROM overrides WHERE id=?',(file_id,)).fetchone()
            if override:
                values=json.loads(override[0]);values.pop('sample_id',None)
                db.execute('UPDATE overrides SET payload=? WHERE id=?',(json.dumps(values),file_id))
            db.execute('UPDATE image_assets SET manual=0,signature=? WHERE file_id=?',('',file_id))
            self.apply(db,json.loads(row[0]),force=True)
            self.families(db)

    def family_members(self, file_id):
        with self.catalog.connect() as db:
            row = db.execute('SELECT family_id FROM image_assets WHERE file_id=?', (file_id,)).fetchone()
            if not row or not row[0]:
                return []
            return [dict(json.loads(p),image_category=c,image_subcategory=s,image_family=row[0]) for p,c,s in db.execute('''
              SELECT f.payload,a.image_category,a.image_subcategory FROM image_assets a JOIN files f ON f.id=a.file_id
              WHERE a.family_id=? ORDER BY a.file_id<>a.original_id,a.image_subcategory''', (row[0],))]

    def summary(self, db):
        return dict(samples_detected=db.execute("SELECT count(*) FROM research_objects WHERE kind='sample' AND project_id=?",(self.project,)).fetchone()[0],
                    sample_relationships=db.execute('SELECT count(*) FROM file_sample_links').fetchone()[0],
                    image_families=db.execute('SELECT count(DISTINCT family_id) FROM image_assets WHERE family_id<>\'\'').fetchone()[0],
                    derived_images_linked=db.execute('SELECT count(*) FROM image_relationships').fetchone()[0],
                    ambiguous_images=db.execute("SELECT count(*) FROM image_assets WHERE image_category='Unknown' OR image_category='Generated / Processed' AND original_id='' ").fetchone()[0])
