"""Readable versioned meeting PDF; no overwrite and output stays in MTG folder."""
import uuid
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from app.services.organization import filename


def export_meeting(service, key, stage):
    row = service.state['records'][key]
    text = service.meeting_text(key, stage)
    folder = service.local / 'exports'
    folder.mkdir(parents=True, exist_ok=True)
    name = filename(row['created_at'], 'meeting', [row['id']], stage + '-' + uuid.uuid4().hex[:8], row['revision'], extension='.pdf')
    target = folder / name
    styles = getSampleStyleSheet()
    styles['BodyText'].leading = 15
    story = [Paragraph(escape(row['title']), styles['Title']), Spacer(1, 0.15 * inch),
             Paragraph(escape(stage.title() + ' · ' + row['id'] + ' · revision ' + str(row['revision'])), styles['Heading2'])]
    for line in text.splitlines():
        story.append(Paragraph(escape(line) if line else '&#160;', styles['BodyText']))
        story.append(Spacer(1, 4))
    def footer(canvas, doc):
        canvas.setFillColor(colors.HexColor('#596579')); canvas.setFont('Helvetica', 9)
        canvas.drawString(0.65 * inch, 0.45 * inch, 'Capstone Hub · Meeting record · ' + str(doc.page))
    with target.open('xb') as stream:
        SimpleDocTemplate(stream, rightMargin=0.65*inch, leftMargin=0.65*inch,
                          topMargin=0.65*inch, bottomMargin=0.7*inch).build(story, onFirstPage=footer, onLaterPages=footer)
    service.upload(target, row['title'] + ' ' + stage, {'meeting_uuid': key, 'file_state': 'reference',
                   'document_type': 'meeting ' + stage, 'created_at': row['created_at']})
    return target
