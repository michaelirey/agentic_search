
import pytest
from cli import process_citations
from types import SimpleNamespace

# Mock classes to simulate OpenAI response objects
class MockFileCitation:
    def __init__(self, file_id, quote):
        self.file_id = file_id
        self.quote = quote

class MockAnnotation:
    def __init__(self, text, start_index, end_index, file_citation=None):
        self.text = text
        self.start_index = start_index
        self.end_index = end_index
        self.file_citation = file_citation

def test_process_citations_basic():
    text = "The system uses vector embeddings 【7†source】 and hybrid search."
    annotations = [
        MockAnnotation(
            text="【7†source】",
            start_index=34,
            end_index=44,
            file_citation=MockFileCitation(file_id="file-123", quote="Vector embeddings are generated...")
        )
    ]
    # Reverse map: file_id -> filename
    file_map = {"file-123": "architecture.md"}
    
    formatted_text, sources = process_citations(text, annotations, file_map)
    
    assert formatted_text == "The system uses vector embeddings [1] and hybrid search."
    assert len(sources) == 1
    assert sources[0]["filename"] == "architecture.md"
    assert sources[0]["quotes"] == ["Vector embeddings are generated..."]
    assert sources[0]["id"] == 1

def test_process_citations_multiple():
    text = "A 【1†source】 B 【2†source】"
    annotations = [
        MockAnnotation(
            text="【1†source】",
            start_index=2,
            end_index=12,
            file_citation=MockFileCitation(file_id="f1", quote="Q1")
        ),
        MockAnnotation(
            text="【2†source】",
            start_index=15,
            end_index=25,
            file_citation=MockFileCitation(file_id="f2", quote="Q2")
        )
    ]
    file_map = {"f1": "doc1.txt", "f2": "doc2.txt"}
    
    formatted_text, sources = process_citations(text, annotations, file_map)
    
    assert formatted_text == "A [1] B [2]"
    assert len(sources) == 2
    assert sources[0]["filename"] == "doc1.txt"
    assert sources[1]["filename"] == "doc2.txt"

def test_process_citations_same_file():
    text = "Start 【1†source】 End 【2†source】"
    annotations = [
        MockAnnotation(
            text="【1†source】",
            start_index=6,
            end_index=16,
            file_citation=MockFileCitation(file_id="f1", quote="Q1")
        ),
        MockAnnotation(
            text="【2†source】",
            start_index=21,
            end_index=31,
            file_citation=MockFileCitation(file_id="f1", quote="Q2")
        )
    ]
    file_map = {"f1": "doc1.txt"}
    
    formatted_text, sources = process_citations(text, annotations, file_map)
    
    assert formatted_text == "Start [1] End [1]"
    assert len(sources) == 1
    assert sources[0]["filename"] == "doc1.txt"
    assert sources[0]["quotes"] == ["Q1", "Q2"]

def test_process_citations_unknown_file():
    text = "Text 【1†source】"
    annotations = [
        MockAnnotation(
            text="【1†source】",
            start_index=5,
            end_index=15,
            file_citation=MockFileCitation(file_id="unknown", quote="Q")
        )
    ]
    file_map = {}
    
    formatted_text, sources = process_citations(text, annotations, file_map)
    
    assert formatted_text == "Text [1]"
    assert sources[0]["filename"] == "Unknown"

def test_process_citations_no_annotations():
    text = "Just text"
    annotations = []
    file_map = {}
    
    formatted_text, sources = process_citations(text, annotations, file_map)
    
    assert formatted_text == "Just text"
    assert len(sources) == 0

