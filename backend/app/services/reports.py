"""PDF exports from immutable, server-owned result snapshots."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from app.core.labels import LABELS


def build_report(record):
    output = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReportTitle', fontName='Helvetica-Bold', fontSize=25,
                              leading=30, textColor=colors.HexColor('#215b4c'), spaceAfter=10))
    styles.add(ParagraphStyle(name='Note', parent=styles['BodyText'], textColor=colors.HexColor('#61776e'),
                              fontSize=10, leading=14, spaceAfter=4))
    result = record['result']
    def paragraph(value, style='BodyText'):
        return Paragraph(escape(str(value)).replace('\n', '<br/>'), styles[style])
    story = [paragraph('LexiTrace', 'ReportTitle'), paragraph('Document authorship assessment', 'Heading2'),
             paragraph(f'Analysis ID: {record["id"]}', 'Note'),
             paragraph(f'Analyzed at (UTC): {record["created_at"]}', 'Note'),
             paragraph(f'Model: {result["model_name"]}', 'Note'),
             paragraph(f'Model version: {result.get("model_version", "Unavailable")}', 'Note'),
             paragraph(f'Input: {result["word_count"]:,} words / {result["character_count"]:,} characters', 'Note'),
             Spacer(1, 12)]
    uncertain = result['confidence'] < 0.6
    story += [paragraph('Assessment: ' + ('Uncertain' if uncertain else result['prediction']), 'Heading2'),
              paragraph(f'Highest-scoring class: {result["prediction"]} ({result["confidence"]:.1%})', 'Note')]
    rows = [['Class', 'Model score']] + [[label, f'{result["class_probabilities"][label]:.1%}'] for label in LABELS]
    table = Table(rows, colWidths=[4.4*inch, 1.6*inch], hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#215b4c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f0f6f2'), colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    story += [table, Spacer(1, 12), paragraph('Explanation', 'Heading2'),
              paragraph('The complete document is assessed using overlapping token windows. The three scores summarize the model response; they are not measured accuracy percentages.', 'BodyText'),
              Spacer(1, 8), paragraph(result.get('explanation_method', 'No explanation available.'))]
    explanation = result.get('explanation')
    if explanation:
        story += [paragraph(explanation.get('method', 'Generated explanation'), 'Heading3'),
                  paragraph(f'Target class: {explanation.get("target_label", "Unavailable")}. {explanation.get("scope", "")}'),
                  Spacer(1, 8)]
        if explanation.get('window_probability') is not None:
            story.append(paragraph(f'Target score in explained window: {explanation["window_probability"]:.1%}', 'Note'))
        if explanation.get('convergence_delta') is not None:
            story.append(paragraph(f'Numerical convergence delta: {explanation["convergence_delta"]:.4g}', 'Note'))
        if explanation.get('approximation_warning'):
            story.append(paragraph('Low explanation reliability: the numerical approximation error is high.', 'Note'))
        story.append(paragraph(explanation.get('disclaimer', ''), 'Note'))
    else:
        story += [Spacer(1, 8), paragraph('A Captum explanation has not been saved for this assessment. Generate one from the current result to include its summary in future downloads.', 'Note')]
    if result.get('sentences'):
        story.append(paragraph('Sentence evidence', 'Heading3'))
        for item in result['sentences']:
            story += [paragraph(f'{item["prediction"]} ({item["score"]:.1%}): {item["sentence"]}'), Spacer(1, 8)]
    else:
        story += [Spacer(1, 8), paragraph('Source excerpts are omitted unless text saving was enabled and sentence evidence was available. Token text and individual token attributions are not stored in reports.', 'Note')]
    story += [Spacer(1, 12), paragraph('Interpretation and limitations', 'Heading2'),
              paragraph(result['disclaimer'], 'Note'),
              paragraph('Use this assessment alongside human review. It does not establish who wrote a document.', 'Note')]
    def footer(canvas, doc):
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.HexColor('#61776e'))
        canvas.drawString(doc.leftMargin, 30, 'LexiTrace | Confidential analysis report')
        canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 30, f'Page {doc.page}')
    SimpleDocTemplate(output, leftMargin=54, rightMargin=54, topMargin=48, bottomMargin=54,
                      title='LexiTrace analysis report', author='LexiTrace').build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
