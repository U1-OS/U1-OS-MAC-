"""Studio contracts run without a server, real accounts, or live managed Files."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import select
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor

from utils import prism_workspace, u1_life_studio, u1_studio_pro as studio


def document():
    return {"title": "Isolated course", "version": "2.1", "template": "course", "source": "Operator test notes",
            "brand": {"name": "Test studio", "accent": "#176B64", "font": "serif"},
            "sections": [{"title": "First lesson", "content": "Operator supplied lesson with an example.", "activity": "Write your own observation.",
                          "quizzes": [{"question": "What did you observe?", "answer_notes": "PRIVATE-QUIZ-NOTES"}], "answer_notes": "PRIVATE-SECTION-NOTES"}],
            "instructions": "Read the lessons. Complete your own answers.", "licence": "Test licence supplied by the operator. No redistribution."}


class Handler:
    def __init__(self, body=None, command="POST", path=studio.ROUTE, allowed=True):
        raw = json.dumps(body if body is not None else {"document": document()}).encode()
        self.path, self.command, self.allowed = path, command, allowed
        self.headers = {"Content-Length": str(len(raw)), "Content-Type": "application/json", "X-U1-CSRF": studio.integrations_hub.CSRF_TOKEN}
        self.rfile, self.wfile = io.BytesIO(raw), io.BytesIO()
        self.status, self.response_headers = None, {}

    def integration_request_allowed(self):
        return self.allowed

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass

    def result(self):
        return json.loads(self.wfile.getvalue())


class RequestTests(unittest.TestCase):
    def test_dispatch_and_get(self):
        handler = Handler(path="/api/workspace/life-studio")
        self.assertFalse(studio.handle_request(handler))
        self.assertIsNone(handler.status)
        handler = Handler(command="GET", path=studio.ROUTE+"?fresh=1")
        self.assertTrue(studio.handle_request(handler))
        self.assertEqual(handler.status, 200)
        self.assertEqual(len(handler.result()["templates"]), 11)
        self.assertEqual(handler.result()["providers"]["canva_sync"], "not_connected")

    def test_origin_token_method_and_mime(self):
        cases = [(Handler(allowed=False),403), (Handler(command="DELETE"),405)]
        for token in ("", "invalid", "\u2603"):
            handler = Handler(); handler.headers["X-U1-CSRF"] = token; cases.append((handler,403))
        handler = Handler(); handler.headers["Content-Type"] = "text/plain"; cases.append((handler,415))
        for handler, status in cases:
            with self.subTest(status=status):
                self.assertTrue(studio.handle_request(handler)); self.assertEqual(handler.status,status)

    def test_malformed_and_bounded_requests(self):
        for raw in (b"{", b"[]", b"null", b' {"action":"render","action":"bundle"}', b"\xff", b"["*1200+b"]"*1200):
            handler = Handler(); handler.rfile = io.BytesIO(raw); handler.headers["Content-Length"] = str(len(raw))
            studio.handle_request(handler); self.assertEqual(handler.status,400)
        for length in ("0", "-1", "wat", str(studio.MAX_REQUEST+1), "999"):
            handler = Handler(); handler.headers["Content-Length"] = length; studio.handle_request(handler); self.assertEqual(handler.status,400)
        handler = Handler(); handler.headers["Transfer-Encoding"] = "chunked"; studio.handle_request(handler); self.assertEqual(handler.status,400)

    def test_valid_route_and_dependency_failure(self):
        handler = Handler({"action":"artwork","document":document()})
        studio.handle_request(handler); self.assertEqual(handler.status,200)
        self.assertEqual(handler.response_headers["Cache-Control"],"no-store")
        self.assertTrue(handler.result()["document"]["fillable"])
        self.assertEqual(handler.result()["document"]["subtitle"],"")
        with patch.object(studio,"canvas",None):
            handler = Handler(); studio.handle_request(handler); self.assertEqual(handler.status,503)
            self.assertTrue(studio.create({"action":"artwork","document":document()})["success"])

    def test_invalid_document_fields(self):
        cases = [("title", "x"*121), ("title", ""), ("title", []), ("title", "bad\x00title"), ("title", "bad\ntitle"), ("title", "\u6c49\u5b57"),
                 ("template", []), ("template", "missing"), ("fillable", 1), ("include_answer_notes", "false"), ("sections", []), ("sections", [{}]*25),
                 ("brand", {"accent":"url(file:///etc/passwd)"}), ("brand", {"font": []}), ("source", "x"*301)]
        for key, value in cases:
            with self.subTest(field=key, value=str(value)[:30]):
                doc = document(); doc[key] = value
                with self.assertRaises(ValueError): studio.create({"document":doc})
        for body in ({"document":document(),"path":"/etc/passwd"}, {"action":[],"document":document()}, {"action":"fetch","document":document()}):
            with self.assertRaises(ValueError): studio.create(body)
        doc = document(); doc["sections"][0]["quizzes"] = [{"question":"test"}]*9
        with self.assertRaises(ValueError): studio.create({"document":doc})
        doc = document(); doc["sections"][0]["quizzes"] = [{"question":""}]
        with self.assertRaises(ValueError): studio.create({"document":doc})
        doc = document(); doc["sections"] = [dict(title="Test",content="x"*6000)]*20
        with self.assertRaises(ValueError): studio.create({"document":doc})


@unittest.skipUnless(studio.canvas and studio.PdfReader, "reportlab and pypdf required")
class PDFTests(unittest.TestCase):
    def generate(self, doc=None, action="render"):
        result = studio.create({"action":action,"document":doc or document()})
        return result, studio.PdfReader(io.BytesIO(base64.b64decode(result["content"]))) if action == "render" else None

    def test_pdf_fields_links_metadata_and_content(self):
        result, reader = self.generate()
        self.assertEqual(result["pages"], len(reader.pages))
        self.assertEqual(set(reader.get_fields()), {"s01_response","s01_q01"})
        self.assertEqual(reader.metadata["/Title"], "Isolated course")
        self.assertEqual(reader.metadata["/U1Version"], "2.1")
        self.assertEqual(reader.metadata["/U1Source"], studio.SOURCE)
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn("Operator supplied lesson",text)
        self.assertNotIn("PRIVATE-",text)
        widgets, links = [], []
        page_ids = {page.indirect_reference.idnum for page in reader.pages}
        for page in reader.pages:
            for ref in page.get("/Annots",[]):
                annotation = ref.get_object()
                if annotation["/Subtype"] == "/Widget": widgets.append(annotation)
                if annotation["/Subtype"] == "/Link":
                    links.append(annotation)
                    self.assertIn(annotation["/Dest"][0].idnum,page_ids)
        self.assertEqual(len(widgets),2)
        for widget in widgets:
            self.assertEqual(widget["/V"], "")
            self.assertIn("/N",widget["/AP"])
            self.assertTrue(int(widget["/Ff"]) & 4096)
        self.assertGreaterEqual(len(links),3)
        self.assertTrue(reader.outline)
        target = result["section_pages"][0]["page"]-1
        self.assertIn("First lesson",reader.pages[target].extract_text())

    def test_form_fill_roundtrip_and_static_variant(self):
        _, reader = self.generate()
        writer = studio.PdfWriter(); writer.clone_document_from_reader(reader)
        writer.update_page_form_field_values(None,{"s01_response":"My saved answer"},auto_regenerate=False)
        target = io.BytesIO(); writer.write(target)
        reread = studio.PdfReader(io.BytesIO(target.getvalue()))
        self.assertEqual(reread.get_fields()["s01_response"]["/V"],"My saved answer")
        for page in reread.pages:
            for ref in page.get("/Annots",[]):
                field = ref.get_object()
                if field.get("/T") == "s01_response":
                    self.assertEqual(field["/V"],"My saved answer"); self.assertIn("/N",field["/AP"])
        doc = document(); doc["fillable"] = False; doc["include_answer_notes"] = True
        result, reader = self.generate(doc)
        self.assertFalse(reader.get_fields()); self.assertEqual(result["fields"],[])
        self.assertIn("PRIVATE-QUIZ-NOTES","\n".join(page.extract_text() for page in reader.pages))

    def test_long_titles_sections_and_content_stay_in_page_bounds(self):
        doc = document(); doc["title"] = "W"*120; doc["brand"]["name"] = "Brand "*13
        doc["sections"] = [{"title":f"Section {i:02d} "+"W"*148,"content":"Continuous "*490+" END-OF-LESSON","quizzes":[]} for i in range(1,15)]
        result, reader = self.generate(doc)
        self.assertGreater(result["section_pages"][0]["page"],3)
        self.assertEqual("\n".join(page.extract_text() for page in reader.pages).count("END-OF-LESSON"),14)
        for page in reader.pages:
            def visitor(text, cm, tm, font, size):
                if text.strip():
                    self.assertGreaterEqual(tm[5],20)
                    self.assertLessEqual(tm[5],float(page.mediabox.height)-15)
            page.extract_text(visitor_text=visitor)
        for row in result["section_pages"]:
            self.assertIn(f"Section {row['index']+1:02d}",reader.pages[row["page"]-1].extract_text())

    def test_legacy_outline_paginates_and_all_templates_survive(self):
        body = {"template":"course","title":"W"*80,"audience":"A"*160,"outline":"\n".join(f"Section {i} "+"W"*149 for i in range(10))}
        result = u1_life_studio.make_document(body)
        reader = studio.PdfReader(io.BytesIO(base64.b64decode(result["content"])))
        self.assertGreater(len(reader.pages),11)
        for page in reader.pages:
            raw = page.get_contents().get_data().decode("ascii")
            for match in re.finditer(r"42 (-?[\d.]+) Td",raw): self.assertGreaterEqual(float(match[1]),30)
            def visitor(value, cm, tm, font, size):
                if value.strip(): self.assertLessEqual(tm[4]+studio.stringWidth(value.rstrip("\n"),"Helvetica",size),553.5)
            page.extract_text(visitor_text=visitor)
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn("Section 9",text)
        from utils import u1_documents
        self.assertEqual(u1_documents.TEMPLATES,{"daily","weekly","workout","meals","calendar","colouring"})
        for template in u1_life_studio.TEMPLATES:
            self.assertTrue(u1_life_studio.make_document({"template":template})["success"])

    def test_pdf_without_pypdf_still_has_forms(self):
        with patch.object(studio,"PdfWriter",None): result = studio.create({"document":document()})
        reader = studio.PdfReader(io.BytesIO(base64.b64decode(result["content"])))
        self.assertEqual(len(reader.get_fields()),2)

    @unittest.skipUnless(studio.pdfium,"pypdfium2 required")
    def test_exact_pdf_page_previews_and_tamper_rejection(self):
        result, reader = self.generate()
        self.assertTrue(base64.b64decode(result["preview"]["content"]).startswith(b"\x89PNG\r\n\x1a\n"))
        request = {"action":"preview","content":result["content"],"signature":result["preview_signature"],"page":3}
        rendered = studio.create(request)
        self.assertEqual(rendered["page"],3)
        self.assertEqual(rendered["content"],studio._preview(base64.b64decode(result["content"]),3)["content"])
        for field,value in (("page",True),("page",0),("page",999),("signature","0"*64),("content",base64.b64encode(b"%PDF-tampered").decode())):
            with self.subTest(field=field):
                with self.assertRaises(ValueError): studio.create({**request,field:value})
        with patch.object(studio,"pdfium",None):
            result = studio.create({"document":document()}); self.assertIsNone(result["preview"])


@unittest.skipUnless(studio.canvas, "reportlab required")
class BundleTests(unittest.TestCase):
    def test_safe_bundle_members_exact_user_text_and_metadata(self):
        for title in ("../../private/secret", "..\\..\\secret", "CON", "<script>alert(1)</script>"):
            doc = document(); doc["title"] = title; doc["version"] = "../../v2"; doc["licence"] = "  Operator licence.\r\nKeep this exact text.\n"
            result = studio.create({"action":"bundle","document":doc})
            self.assertNotRegex(result["filename"],r"[\\/]")
            with zipfile.ZipFile(io.BytesIO(base64.b64decode(result["content"]))) as archive:
                self.assertEqual(len(archive.namelist()),7)
                for name in archive.namelist():
                    self.assertNotIn("/",name); self.assertNotIn("\\",name); self.assertNotIn("..",name)
                self.assertEqual(archive.read("LICENCE.txt").decode(),doc["licence"])
                self.assertEqual(archive.read("INSTRUCTIONS.txt").decode(),doc["instructions"])
                metadata = json.loads(archive.read("metadata.json"))
                self.assertEqual(metadata["title"],title); self.assertEqual(metadata["version"],"../../v2")
                self.assertFalse(metadata["ai_generated"])
                for name in archive.namelist():
                    if name.endswith(".svg"):
                        xml = ET.fromstring(archive.read(name)); self.assertNotIn("script",[element.tag.split('}')[-1] for element in xml.iter()])
                        for span in xml.iter("{http://www.w3.org/2000/svg}tspan"):
                            self.assertLessEqual(float(span.attrib["textLength"]),736)
                pdf_name = next(name for name in archive.namelist() if name.endswith(".pdf"))
                if studio.PdfReader:
                    reader = studio.PdfReader(io.BytesIO(archive.read(pdf_name)))
                    self.assertNotIn("PRIVATE-","\n".join(page.extract_text() for page in reader.pages))

    def test_bundle_requires_operator_instructions_and_licence(self):
        for key in ("instructions","licence"):
            doc = document(); doc[key] = ""
            with self.assertRaises(ValueError): studio.create({"action":"bundle","document":doc})

    def test_generated_bundle_roundtrip_through_isolated_managed_files(self):
        result = studio.create({"action":"bundle","document":document()}); raw = base64.b64decode(result["content"])
        with tempfile.TemporaryDirectory(prefix="u1-studio-test-") as temp, patch.object(prism_workspace,"DATA",Path(temp)):
            start = prism_workspace.handle_post("prism/upload-start",{"name":result["filename"],"mime":result["mime"],"size":len(raw),"folder":"Digital Studio"})
            for offset in range(0,len(raw),32768):
                uploaded = prism_workspace.handle_post("prism/upload-chunk",{"id":start["id"],"offset":offset,"content":base64.b64encode(raw[offset:offset+32768]).decode()})
            self.assertEqual(uploaded["status"],"ready")
            self.assertEqual((Path(temp)/"files"/start["id"]).read_bytes(),raw)


class FrontendContractTests(unittest.TestCase):
    def test_actual_js_saves_exact_32kb_chunks_and_rejects_incomplete_confirmation(self):
        script = Path(__file__).resolve().parents[1]/"static/js/u1-studio-pro.js"
        harness = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let calls=[],fail=false;
global.window={U1CoreViews:{register:(id,fn)=>assert.equal(id,'studio')},U1Data:{post:async(path,body)=>{
 calls.push({path,body});
 if(path.endsWith('upload-start'))return {success:true,id:'isolated-id'};
 const received=body.offset+Buffer.from(body.content,'base64').length;
 return {success:true,received:fail?0:received,status:received===70003?'ready':'uploading'};
}}};
vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));
(async()=>{
 const original=Buffer.alloc(70003);for(let i=0;i<original.length;i++)original[i]=i%251;
 const artifact={filename:'u1-test-v1.pdf',mime:'application/pdf',content:original.toString('base64')};
 const saved=await window.U1StudioPro.saveFile(artifact);
 assert.equal(saved.size,70003);assert.equal(calls.length,4);
 assert.deepEqual(calls.slice(1).map(x=>x.body.offset),[0,32768,65536]);
 assert.deepEqual(calls.slice(1).map(x=>Buffer.from(x.body.content,'base64').length),[32768,32768,4467]);
 assert.deepEqual(Buffer.concat(calls.slice(1).map(x=>Buffer.from(x.body.content,'base64'))),original);
 assert.equal(calls[0].body.folder,'Digital Studio');
 calls=[];await assert.rejects(()=>window.U1StudioPro.saveFile({...artifact,filename:'../unsafe.pdf'}));assert.equal(calls.length,0);
 fail=true;await assert.rejects(()=>window.U1StudioPro.saveFile(artifact),/Save incomplete/);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        completed = subprocess.run(["node","-e",harness,str(script)],capture_output=True,text=True,timeout=20)
        self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)


@unittest.skipUnless(studio.canvas and studio.PdfReader and studio.pdfium,
                     "reportlab, pypdf and pypdfium2 required for integration acceptance")
class ManagedFilesAcceptanceTests(unittest.TestCase):
    """Actual JS -> pipe transport -> fixtures -> isolated PRISM database.

    No HTTP server, network requests, live app import, account calls, or real
    workspace data. The dispatcher below represents only the approved route
    fixtures; it does not claim to test the parent's live HTTP dispatch chain.
    """

    @classmethod
    def setUpClass(cls):
        cls.doc = document()
        cls.doc.update(title="Managed Files acceptance", version="3.0",
                       instructions="Read each lesson.\r\nComplete your own responses.\n",
                       licence="  Operator-supplied acceptance licence.\nNo redistribution.\n")
        cls.doc["sections"] = [
            {"title": f"Acceptance section {index:02d}",
             "content": "Operator-written fixture for isolated acceptance. "*8,
             "activity": "Write your own observation.",
             "answer_notes": "Excluded operator section notes.",
             "quizzes": [{"question": f"Question {number}: describe an observation for section {index}.",
                          "answer_notes": f"Excluded operator answer {index}/{number}."}
                         for number in range(1,9)]}
            for index in range(1,25)
        ]
        cls.artifacts = []
        for action in ("render", "bundle"):
            handler = Handler({"action": action, "document": cls.doc})
            if not studio.handle_request(handler) or handler.status != 200:
                raise AssertionError(f"Studio fixture {action} failed: {handler.wfile.getvalue()[:500]!r}")
            cls.artifacts.append(handler.result())
        cls.pdf, cls.bundle = cls.artifacts
        if cls.pdf["size"] <= 2*32768:
            raise AssertionError("Acceptance PDF must exercise at least three actual upload chunks")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="u1-studio-acceptance-")
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)/"prism"
        data_patch = patch.object(prism_workspace,"DATA",self.data)
        data_patch.start(); self.addCleanup(data_patch.stop)
        profile_patch = patch.object(prism_workspace,"PROFILE",{"name":"Acceptance fixture","timezone":"UTC"})
        profile_patch.start(); self.addCleanup(profile_patch.stop)
        self.calls = []

    def dispatch(self, path, body):
        handler = Handler(body,path=path)
        if studio.handle_request(handler):
            return handler.status, handler.result()
        self.assertIn(path,{"/api/workspace/prism/upload-start","/api/workspace/prism/upload-chunk"})
        from utils.u1_safety import _reply
        try:
            _reply(handler,prism_workspace.handle_post(path,json.load(handler.rfile)))
        except (ValueError,TypeError) as error:
            _reply(handler,{"success":False,"error":str(error)},400)
        self.calls.append({"path":path,"body":body,"status":handler.status,"response":handler.result()})
        return handler.status, handler.result()

    def run_actual_js_uploads(self):
        script = Path(__file__).resolve().parents[1]/"static/js/u1-studio-pro.js"
        harness = r'''
const fs=require('fs'),vm=require('vm'),readline=require('readline');
const input=readline.createInterface({input:process.stdin,crlfDelay:Infinity});
const pending=[];
global.window={U1CoreViews:{register:()=>{}},U1Data:{post:(path,body)=>new Promise((resolve,reject)=>{
 pending.push({resolve,reject});process.stdout.write(JSON.stringify({request:{path,body}})+'\n');
})}};
vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));
async function run(artifacts){
 try{
  const saved=[];
  for(const artifact of artifacts)saved.push(await window.U1StudioPro.saveFile(artifact));
  process.stdout.write(JSON.stringify({saved})+'\n');
 }catch(error){process.stdout.write(JSON.stringify({failure:error.message})+'\n');process.exitCode=1;}
 finally{input.close();process.stdin.pause();}
}
input.on('line',line=>{
 const message=JSON.parse(line);
 if(message.artifacts){run(message.artifacts);return;}
 const waiting=pending.shift();
 if(!waiting)throw Error('Unexpected transport reply');
 if(message.success===false)waiting.reject(Error(message.error));else waiting.resolve(message);
});
'''
        process = subprocess.Popen(["node","-e",harness,str(script)],stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        try:
            # Only generated artifact data enters the child; no account tokens or
            # user paths are passed to its U1Data transport.
            inputs = [{key:artifact[key] for key in ("filename","mime","content")} for artifact in self.artifacts]
            process.stdin.write(json.dumps({"artifacts":inputs})+"\n"); process.stdin.flush()
            while True:
                ready,_,_ = select.select([process.stdout],[],[],20)
                self.assertTrue(ready,"JavaScript upload timed out waiting for a fixture call")
                line = process.stdout.readline()
                self.assertTrue(line,"JavaScript upload stopped before reporting saved files")
                message = json.loads(line)
                self.assertNotIn("failure",message,message.get("failure"))
                if "saved" in message:
                    saved = message["saved"]
                    break
                request = message["request"]
                _, response = self.dispatch(request["path"],request["body"])
                process.stdin.write(json.dumps(response)+"\n"); process.stdin.flush()
            process.stdin.close()
            process.wait(timeout=10)
            self.assertEqual(process.returncode,0,process.stderr.read())
            return saved
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=5)
            for stream in (process.stdin,process.stdout,process.stderr):
                if stream and not stream.closed: stream.close()

    def test_actual_js_pdf_and_zip_saved_downloaded_and_exported(self):
        saved = self.run_actual_js_uploads()
        self.assertEqual(len(saved),2)
        rows = {row["id"]:row for row in prism_workspace.files()}
        self.assertEqual(len(rows),2)
        evidence = []
        for artifact,stored in zip(self.artifacts,saved):
            raw = base64.b64decode(artifact["content"],validate=True)
            row = rows[stored["id"]]
            self.assertEqual(row["status"],"ready")
            self.assertEqual(row["received"],len(raw)); self.assertEqual(row["size"],len(raw))
            self.assertEqual(row["checksum"],hashlib.sha256(raw).hexdigest())
            self.assertEqual(row["checksum"],artifact["sha256"])
            self.assertEqual(row["name"],artifact["filename"])
            self.assertEqual(row["mime"],artifact["mime"])
            self.assertEqual(row["folder"],"Digital Studio")
            self.assertEqual((self.data/"files"/row["id"]).read_bytes(),raw)
            chunks = [call for call in self.calls if call["path"].endswith("upload-chunk") and call["body"]["id"] == row["id"]]
            self.assertEqual([call["body"]["offset"] for call in chunks],list(range(0,len(raw),32768)))
            reconstructed = []
            for index,call in enumerate(chunks):
                chunk = base64.b64decode(call["body"]["content"],validate=True)
                self.assertEqual(len(chunk),min(32768,len(raw)-index*32768))
                self.assertEqual(call["status"],200)
                self.assertEqual(call["response"]["received"],index*32768+len(chunk))
                self.assertEqual(call["response"]["status"],"ready" if index == len(chunks)-1 else "uploading")
                reconstructed.append(chunk)
            self.assertEqual(b"".join(reconstructed),raw)
            downloaded = prism_workspace.handle_get("prism/file",{"id":[row["id"]]})
            self.assertEqual(base64.b64decode(downloaded["content"],validate=True),raw)
            evidence.append({"mime":row["mime"],"bytes":len(raw),"chunks":len(chunks),
                             "last_offset":chunks[-1]["body"]["offset"],"received":row["received"],"status":row["status"]})

        exported = prism_workspace.handle_get("prism/export",{})
        self.assertEqual(exported["format"],"prism-workspace-backup")
        self.assertEqual(exported["records"],[]); self.assertEqual(exported["trash"],[])
        self.assertEqual({row["id"] for row in exported["files"]},set(rows))
        for row in exported["files"]:
            self.assertEqual(row["status"],"ready"); self.assertEqual(row["checksum"],rows[row["id"]]["checksum"])
        self.assertIn("File metadata only",exported["notice"])

        downloaded_pdf = prism_workspace.handle_get("prism/file",{"id":[saved[0]["id"]]})
        code, preview = self.dispatch(studio.ROUTE,{"action":"preview","content":downloaded_pdf["content"],
                                                  "signature":self.pdf["preview_signature"],"page":self.pdf["section_pages"][-1]["page"]})
        self.assertEqual(code,200)
        self.assertTrue(base64.b64decode(preview["content"]).startswith(b"\x89PNG\r\n\x1a\n"))
        reader = studio.PdfReader(io.BytesIO(base64.b64decode(downloaded_pdf["content"])))
        self.assertEqual(reader.metadata["/Title"],self.doc["title"])
        self.assertEqual(reader.metadata["/U1Version"],self.doc["version"])
        self.assertEqual(reader.metadata["/U1Source"],studio.SOURCE)
        self.assertEqual(set(reader.get_fields()),set(self.pdf["fields"]))

        downloaded_zip = prism_workspace.handle_get("prism/file",{"id":[saved[1]["id"]]})
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(downloaded_zip["content"]))) as archive:
            self.assertEqual(archive.testzip(),None)
            self.assertEqual(set(archive.namelist()),set(self.bundle["members"]))
            self.assertEqual(archive.read("LICENCE.txt").decode(),self.doc["licence"])
            self.assertEqual(archive.read("INSTRUCTIONS.txt").decode(),self.doc["instructions"])
            metadata = json.loads(archive.read("metadata.json"))
            self.assertEqual(metadata["title"],self.doc["title"])
            self.assertEqual(metadata["version"],self.doc["version"])
            self.assertEqual(metadata["source"],studio.SOURCE)
            bundled_reader = studio.PdfReader(io.BytesIO(archive.read(next(name for name in archive.namelist() if name.endswith(".pdf")))))
            self.assertEqual(len(bundled_reader.pages),self.bundle["pages"])
            self.assertEqual(set(bundled_reader.get_fields()),set(self.bundle["fields"]))
            self.assertNotIn("Excluded operator","\n".join(page.extract_text() for page in bundled_reader.pages))
        print("\nMANAGED_FILES_ACCEPTANCE "+json.dumps({"files":evidence,"pdf_pages":len(reader.pages),
              "form_fields":len(reader.get_fields()),"signed_download_preview_page":preview["page"],"metadata_export_files":len(exported["files"])},sort_keys=True))

    def test_invalid_chunks_never_advance_or_publish_partial_pdf(self):
        raw = base64.b64decode(self.pdf["content"])
        _, start = self.dispatch("/api/workspace/prism/upload-start",{"name":self.pdf["filename"],"mime":"application/pdf","size":len(raw),"folder":"Digital Studio"})
        first = base64.b64encode(raw[:32768]).decode()
        code, partial = self.dispatch("/api/workspace/prism/upload-chunk",{"id":start["id"],"offset":0,"content":first})
        self.assertEqual(code,200); self.assertEqual(partial["status"],"uploading")
        with self.assertRaises(ValueError): prism_workspace.handle_get("prism/file",{"id":[start["id"]]})
        for offset, content in ((0,first),(65536,first),(32768,"not base64!"),(32768,base64.b64encode(b"x"*32769).decode())):
            code, rejected = self.dispatch("/api/workspace/prism/upload-chunk",{"id":start["id"],"offset":offset,"content":content})
            self.assertEqual(code,400); self.assertFalse(rejected["success"])
            row = prism_workspace.files()[0]
            self.assertEqual(row["received"],32768); self.assertEqual(row["status"],"uploading")
            self.assertIsNone(row["checksum"])
            self.assertEqual((self.data/"files"/start["id"]).read_bytes(),raw[:32768])
        for offset in range(32768,len(raw),32768):
            code, reply = self.dispatch("/api/workspace/prism/upload-chunk",{"id":start["id"],"offset":offset,"content":base64.b64encode(raw[offset:offset+32768]).decode()})
            self.assertEqual(code,200)
        self.assertEqual(reply["status"],"ready"); self.assertEqual(reply["received"],len(raw))
        code, rejected = self.dispatch("/api/workspace/prism/upload-chunk",{"id":start["id"],"offset":len(raw),"content":""})
        self.assertEqual(code,400)
        self.assertEqual(prism_workspace.files()[0]["checksum"],self.pdf["sha256"])

    def test_signature_survives_download_but_rejects_tampering_and_restart(self):
        request = {"action":"preview","content":self.pdf["content"],"signature":self.pdf["preview_signature"],"page":2}
        handler = Handler(request)
        studio.handle_request(handler); self.assertEqual(handler.status,200)
        tampered = bytearray(base64.b64decode(self.pdf["content"])); tampered[-12] ^= 1
        cases = [{**request,"content":base64.b64encode(tampered).decode()},
                 {**request,"content":self.bundle["content"]},
                 {**request,"page":True},{**request,"page":self.pdf["pages"]+1}]
        for body in cases:
            handler = Handler(body)
            studio.handle_request(handler); self.assertEqual(handler.status,400)
        with patch.object(studio,"_PREVIEW_KEY",b"isolated-restarted-process-key"):
            handler = Handler(request)
            studio.handle_request(handler); self.assertEqual(handler.status,400)
        handler = Handler(request); handler.headers["X-U1-CSRF"] = "wrong-fixture-token"
        studio.handle_request(handler); self.assertEqual(handler.status,403)
        handler = Handler(request,allowed=False)
        studio.handle_request(handler); self.assertEqual(handler.status,403)


@unittest.skipUnless(studio.canvas and studio.PdfReader,"Studio PDF dependencies required")
class CatalogueHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = studio.create({"document":document()})
        cls.bundle = studio.create({"action":"bundle","document":document()})

    def setUp(self):
        from utils import u1_personal_core
        self.personal = u1_personal_core
        self.temp = tempfile.TemporaryDirectory(prefix="u1-studio-catalogue-")
        self.addCleanup(self.temp.cleanup)
        data_patch = patch.object(prism_workspace,"DATA",Path(self.temp.name))
        data_patch.start(); self.addCleanup(data_patch.stop)
        self.file_id = self.upload(self.artifact)

    def upload(self,artifact,complete=True):
        raw = base64.b64decode(artifact["content"])
        started = prism_workspace.handle_post("prism/upload-start",{"name":artifact["filename"],"mime":artifact["mime"],"size":len(raw),"folder":"Digital Studio"})
        if complete:
            for offset in range(0,len(raw),32768):
                prism_workspace.handle_post("prism/upload-chunk",{"id":started["id"],"offset":offset,"content":base64.b64encode(raw[offset:offset+32768]).decode()})
        return started["id"]

    def post(self,body,status=200):
        handler = Handler(body)
        self.assertTrue(studio.handle_request(handler))
        self.assertEqual(handler.status,status,handler.result())
        return handler.result()

    def review(self,file_id=None,artifact=None):
        return self.post({"action":"handoff-review","file_id":file_id or self.file_id,"receipt":(artifact or self.artifact)["handoff_receipt"]})

    def request(self,review=None,file_id=None,artifact=None,checklist=None):
        review = review or self.review(file_id,artifact)
        return {"action":"handoff","file_id":file_id or self.file_id,"receipt":(artifact or self.artifact)["handoff_receipt"],
                "reviewed":True,"product":review["product"],"expected_product_version":review["expected_product_version"],"checklist":checklist or []}

    def rows(self,kind):
        return self.personal.snapshot({"kind":kind,"archived":"all"})["records"]

    def test_review_creates_nothing_and_confirmation_links_real_ready_file(self):
        review = self.review()
        self.assertEqual(review["file"]["status"],"ready")
        self.assertEqual(review["artifact"]["version"],document()["version"])
        self.assertFalse(review["publishes"]); self.assertEqual(self.rows("product"),[])
        request = self.request(review)
        self.post({**request,"reviewed":False},400)
        self.assertEqual(self.rows("product"),[])
        created = self.post(request)
        row = created["product"]
        self.assertEqual(row["kind"],"product")
        self.assertEqual(row["payload"]["status"],"review")
        self.assertEqual(row["payload"]["current_version"],document()["version"])
        self.assertEqual(row["payload"]["versions"][0]["file_id"],self.file_id)
        self.assertIn(self.artifact["sha256"],row["payload"]["versions"][0]["notes"])
        self.assertEqual(created["launches"],[]); self.assertEqual(self.rows("launch"),[])
        retry = self.post(request)
        self.assertTrue(retry["reused"]); self.assertEqual(retry["product"]["id"],row["id"])
        self.assertEqual(len(self.rows("product")),1)

    def test_concurrent_retries_create_one_product_and_only_approved_tasks(self):
        request = self.request(checklist=["Review content","Review rights"])
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _:studio.create(copy.deepcopy(request)),range(8)))
        self.assertEqual(len({result["product"]["id"] for result in results}),1)
        self.assertEqual(sum(not result["reused"] for result in results),1)
        self.assertEqual(len(self.rows("product")),1)
        tasks = self.rows("launch")
        self.assertEqual({row["title"] for row in tasks},{"Review content","Review rights"})
        self.assertTrue(all(row["payload"]["status"] == "backlog" for row in tasks))
        self.assertTrue(all(row["payload"]["product_id"] == results[0]["product"]["id"] for row in tasks))
        self.assertTrue(all(result["publishes"] is False for result in results))

    def test_pdf_and_zip_share_product_and_repeated_link_is_idempotent(self):
        created = self.post(self.request())
        zip_id = self.upload(self.bundle)
        review = self.review(zip_id,self.bundle)
        self.assertEqual(review["existing"]["id"],created["product"]["id"])
        request = self.request(review,zip_id,self.bundle)
        linked = self.post(request)
        self.assertTrue(linked["reused"])
        self.assertEqual({v["file_id"] for v in linked["product"]["payload"]["versions"]},{self.file_id,zip_id})
        repeated = self.post(request)
        self.assertEqual(repeated["product"]["id"],created["product"]["id"])
        self.assertEqual(len(repeated["product"]["payload"]["versions"]),2)
        self.assertEqual(len(self.rows("product")),1)

    def test_wrong_unready_trashed_or_tampered_files_rejected(self):
        unready = self.upload(self.artifact,complete=False)
        request = {"action":"handoff-review","file_id":unready,"receipt":self.artifact["handoff_receipt"]}
        self.post(request,400)
        wrong = self.upload(self.bundle)
        self.post({**request,"file_id":wrong},400)
        self.post({**request,"file_id":"a"*32},400)
        forged = copy.deepcopy(self.artifact["handoff_receipt"]); forged["artifact"]["version"] = "Unreviewed version"
        self.post({**request,"file_id":self.file_id,"receipt":forged},400)
        review = self.review()
        prism_workspace.handle_post("prism/trash",{"id":self.file_id,"kind":"file"})
        self.post(self.request(review),400)
        self.assertEqual(self.rows("product"),[])

    def test_partial_checklist_retry_preserves_product_and_completed_tasks(self):
        request = self.request(checklist=["First task","Second task"])
        original = self.personal.action
        def fail_second(body):
            if body.get("kind") == "launch" and body.get("title") == "Second task":
                raise self.personal.PersonalError("Isolated fixture record limit",409,"record_limit")
            return original(body)
        with patch.object(self.personal,"action",side_effect=fail_second):
            partial = self.post(request)
        self.assertTrue(partial["partial"])
        self.assertEqual(partial["pending_checklist"],["Second task"])
        self.assertEqual(len(self.rows("product")),1); self.assertEqual(len(self.rows("launch")),1)
        retried = self.post(request)
        self.assertFalse(retried["partial"]); self.assertTrue(retried["reused"])
        self.assertEqual(retried["product"]["id"],partial["product"]["id"])
        self.assertEqual(len(self.rows("product")),1); self.assertEqual(len(self.rows("launch")),2)

    def test_conflicts_archives_and_bounded_operator_fields(self):
        request = self.request()
        for bad in ({"checklist":["Same"]*2},{"checklist":[str(i) for i in range(7)]},{"checklist":["x"*161]},
                    {"expected_product_version":False},{"product":{"title":"x"*161}},{"publish":True}):
            self.post({**request,**bad},400)
        self.assertEqual(self.rows("product"),[])
        row = self.post(request)["product"]
        reviewed = self.review()
        changed = self.personal.action({"action":"update","id":row["id"],"expected_version":row["version"],"title":"Changed elsewhere"})["record"]
        self.post(self.request(reviewed),409)
        self.personal.action({"action":"archive","id":changed["id"],"expected_version":changed["version"]})
        self.post({"action":"handoff-review","file_id":self.file_id,"receipt":self.artifact["handoff_receipt"]},400)
        self.assertEqual(len(self.rows("product")),1)


if __name__ == "__main__":
    unittest.main()
