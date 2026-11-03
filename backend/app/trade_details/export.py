"""Small native XLSX writer: explicit inline strings prevent formula injection."""
from io import BytesIO
from zipfile import ZipFile,ZIP_DEFLATED
from decimal import Decimal
from xml.sax.saxutils import escape

def workbook(headers,rows):
    def cell(value):
        if isinstance(value,(int,Decimal)) and not isinstance(value,bool):return '<c><v>'+str(value)+'</v></c>'
        text='' if value is None else str(value)
        text=''.join(c for c in text if c in '\t\n\r' or ord(c)>=32)
        return '<c t="inlineStr"><is><t xml:space="preserve">'+escape(text)+'</t></is></c>'
    xml='<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    xml+=''.join('<row>'+''.join(cell(v) for v in row)+'</row>' for row in [headers,*rows])+'</sheetData></worksheet>'
    out=BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Trade History" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml',xml)
    return out.getvalue()
