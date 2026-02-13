"""PDF generation using ReportLab."""

import logging
from io import BytesIO
from typing import Dict, Any, Optional, List
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

logger = logging.getLogger(__name__)


class PDFGenerator:
    """PDF generator using ReportLab."""
    
    def __init__(self):
        """Initialize PDF generator with default styles."""
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        # Custom title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2E3B4E')
        ))
        
        # Custom subtitle style
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=20,
            textColor=colors.HexColor('#4A5568')
        ))
        
        # Custom body text with better spacing
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            leading=14
        ))
    
    def create_simple_pdf(
        self,
        title: str,
        content: str,
        author: Optional[str] = None,
        subject: Optional[str] = None
    ) -> bytes:
        """
        Create a simple PDF with title and content.
        
        Args:
            title: Document title
            content: Main content text
            author: Document author
            subject: Document subject
            
        Returns:
            PDF content as bytes
        """
        buffer = BytesIO()
        
        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Set document metadata
        if author:
            doc.author = author
        if subject:
            doc.subject = subject
        doc.title = title
        doc.creator = "ARIS File Creator"
        
        # Build document content
        story = []
        
        # Add title
        story.append(Paragraph(title, self.styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        story.append(Paragraph(f"Generated: {timestamp}", self.styles['Normal']))
        story.append(Spacer(1, 30))
        
        # Add content paragraphs
        paragraphs = content.split('\n\n')
        for paragraph in paragraphs:
            if paragraph.strip():
                story.append(Paragraph(paragraph.strip(), self.styles['CustomBody']))
                story.append(Spacer(1, 12))
        
        # Build PDF
        try:
            doc.build(story)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            logger.info(f"✅ Generated simple PDF: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"❌ PDF generation failed: {str(e)}")
            buffer.close()
            raise
    
    def create_report_pdf(
        self,
        title: str,
        sections: List[Dict[str, Any]],
        author: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Create a structured report PDF with sections and tables.
        
        Args:
            title: Report title
            sections: List of sections with titles and content
            author: Report author
            metadata: Additional metadata for the report
            
        Returns:
            PDF content as bytes
        """
        buffer = BytesIO()
        
        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Set document metadata
        if author:
            doc.author = author
        doc.title = title
        doc.subject = "Manufacturing Report"
        doc.creator = "ARIS File Creator"
        
        # Build document content
        story = []
        
        # Add title
        story.append(Paragraph(title, self.styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        # Add metadata if provided
        if metadata:
            story.append(Paragraph("Report Information", self.styles['CustomSubtitle']))
            for key, value in metadata.items():
                story.append(Paragraph(f"<b>{key}:</b> {value}", self.styles['CustomBody']))
            story.append(Spacer(1, 20))
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        story.append(Paragraph(f"<b>Generated:</b> {timestamp}", self.styles['CustomBody']))
        story.append(Spacer(1, 30))
        
        # Add sections
        for section in sections:
            section_title = section.get('title', 'Untitled Section')
            section_content = section.get('content', '')
            section_data = section.get('data', None)
            
            # Add section title
            story.append(Paragraph(section_title, self.styles['CustomSubtitle']))
            story.append(Spacer(1, 12))
            
            # Add section content
            if section_content:
                story.append(Paragraph(section_content, self.styles['CustomBody']))
                story.append(Spacer(1, 12))
            
            # Add table data if provided
            if section_data and isinstance(section_data, list) and section_data:
                table = self._create_table(section_data)
                story.append(table)
                story.append(Spacer(1, 20))
        
        # Build PDF
        try:
            doc.build(story)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            logger.info(f"✅ Generated report PDF: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"❌ Report PDF generation failed: {str(e)}")
            buffer.close()
            raise
    
    def _create_table(self, data: List[Dict[str, Any]]) -> Table:
        """Create a formatted table from data."""
        if not data:
            return Table([["No data available"]])
        
        # Extract headers from first row
        headers = list(data[0].keys())
        
        # Build table data
        table_data = [headers]  # Header row
        for row in data:
            table_data.append([str(row.get(header, '')) for header in headers])
        
        # Create table
        table = Table(table_data)
        
        # Apply table style
        table.setStyle(TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A5568')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            
            # Body style
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        return table
