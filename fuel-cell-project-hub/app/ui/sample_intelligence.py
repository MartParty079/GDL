"""Manual sample relationships and image classifications, independent of source paths."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLabel,QListWidget,QListWidgetItem,
                               QComboBox,QDialogButtonBox,QLineEdit,QPushButton,QInputDialog)
from app.services.sample_intelligence import SampleIntelligence, normalize
from app.services.storage import timestamp
from app.services.research_workspace import ResearchWorkspace


class RelationshipEditor(QDialog):
    def __init__(self, catalog, row, parent=None):
        super().__init__(parent)
        self.catalog,self.row = catalog,row
        self.service=SampleIntelligence(catalog)
        self.setWindowTitle('Sample and image relationships')
        self.resize(620,620)
        layout=QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addWidget(QLabel('Confirmed choices survive rescans. Uncheck all to remove assignments.'))
        selected={r['id'] for r in self.service.related_samples(row['id'])}
        self.samples=QListWidget()
        for sample in ResearchWorkspace(catalog).objects('sample',row['data_origin']):
            item=QListWidgetItem(sample['name'])
            item.setData(Qt.UserRole,sample['id'])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if sample['id'] in selected else Qt.Unchecked)
            self.samples.addItem(item)
        layout.addWidget(self.samples)
        form=QFormLayout();layout.addLayout(form)
        self.relationship=QComboBox();self.relationship.addItems(['primary','contains','compares','derived_from','references'])
        form.addRow('Sample relationship',self.relationship)
        self.category=QComboBox();self.subtype=QComboBox();self.original=QComboBox()
        self.subtype.addItem('Unspecified','')
        self.original.addItem('Original Not Located','')
        self.is_image=row['extension'] in ('.png','.jpg','.jpeg','.tif','.tiff','.bmp','.gif','.webp')
        if self.is_image:
            with catalog.connect() as db:
                for name,parent_id in db.execute('SELECT name,parent_id FROM asset_categories WHERE active=1 ORDER BY sort_order'):
                    (self.subtype if parent_id else self.category).addItem(name,name)
                asset=db.execute('SELECT image_category,image_subcategory,original_id FROM image_assets WHERE file_id=?',(row['id'],)).fetchone()
                for identity,name in db.execute('''SELECT m.id,m.name FROM file_metadata m JOIN image_assets a ON a.file_id=m.id
                  WHERE m.source_id=? AND m.data_origin=? AND a.image_category='Original' AND m.id<>? ORDER BY m.name LIMIT 2000''',
                    (row['source_id'],row['data_origin'],row['id'])):
                    self.original.addItem(name,identity)
            if asset:
                self.category.setCurrentIndex(max(0,self.category.findData(asset[0])))
                self.subtype.setCurrentIndex(max(0,self.subtype.findData(asset[1])))
                self.original.setCurrentIndex(max(0,self.original.findData(asset[2])))
            form.addRow('Image category',self.category);form.addRow('Subcategory',self.subtype)
            form.addRow('Link Original',self.original)
            self.original_search=QLineEdit();self.original_search.setPlaceholderText('Search originals by name')
            form.addRow('Find original',self.original_search)
            self.original_search.textChanged.connect(self.find_original)
        self.error=QLabel();self.error.setWordWrap(True);layout.addWidget(self.error)
        alias=QPushButton('Add sample alias');alias.clicked.connect(self.add_alias);layout.addWidget(alias)
        category=QPushButton('Add image subcategory');category.clicked.connect(self.add_category);layout.addWidget(category)
        reset=QPushButton('Reset this file to automatic classification')
        reset.clicked.connect(lambda:(self.service.reset(self.row['id']),self.accept()))
        layout.addWidget(reset)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def find_original(self, text):
        self.original.clear();self.original.addItem('Original Not Located','')
        rows,_=self.catalog.query(text,origin=self.row['data_origin'],source_id=self.row['source_id'],image_category='Original',limit=200)
        for row in rows:
            if row['id']!=self.row['id']:
                self.original.addItem(row['name'],row['id'])

    def add_alias(self):
        item=self.samples.currentItem()
        if not item:
            self.error.setText('Select a sample first.');return
        alias,ok=QInputDialog.getText(self,'Add alias','Supported sample name or identifier:')
        if ok and normalize(alias) and not normalize(alias).isdigit():
            with self.catalog.connect() as db:
                db.execute('INSERT OR REPLACE INTO sample_aliases VALUES (?,?,?,?,?,1)',
                           (item.data(Qt.UserRole),alias,normalize(alias),'manual','HIGH'))

    def add_category(self):
        name,ok=QInputDialog.getText(self,'Image subcategory','Name:')
        if ok and name.strip():
            with self.catalog.connect() as db:
                db.execute('INSERT OR IGNORE INTO asset_categories VALUES (?,?,?,?,1,100)',(normalize(name),name.strip(),'generated','Image'))
            if self.is_image:self.subtype.addItem(name.strip(),name.strip())

    def save(self):
        try:
            samples=[self.samples.item(i).data(Qt.UserRole) for i in range(self.samples.count()) if self.samples.item(i).checkState()==Qt.Checked]
            self.service.assign(self.row['id'],samples,self.relationship.currentText())
            if self.is_image:
                self.service.edit_image(self.row['id'],self.category.currentText(),self.subtype.currentData(),self.original.currentData())
            self.accept()
        except ValueError as exc:
            self.error.setText(str(exc))
