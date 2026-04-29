# import os
# import sys

# from dotenv import load_dotenv
# load_dotenv()
# pythonpath = os.getenv("PYTHONPATH")
# if pythonpath:
#     full_path = os.path.abspath(pythonpath)
#     if full_path not in sys.path:
#         sys.path.insert(0, full_path)

import re
import pandas as pd
import hashlib
import json
import pymysql
import requests
import mimetypes
import logging

from jira import JIRA
from pathlib import Path
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

AUTHORIZATION = "Bearer NDcwMjEwNDU0NjU0Olkunv7VJrh+a0YGT9kq8f4tQI5G"
JIRA_token = 'NDcwMjEwNDU0NjU0Olkunv7VJrh+a0YGT9kq8f4tQI5G'


class ReportParserToJira(object):
    def __init__(self,fullPath,itemName) -> None:
        host = 'capx-sm.capx.com'
        port = 3306
        user = 'test'
        password = 'P@ss1234'
        dbName = 'RegressShield'
        self.dbconnection = MysqlConnection(host,port,user,password,dbName)

        self.fullPath = fullPath
        self.itemName = itemName
        
        # Check if fullPath is a URL or local path
        self.is_url = str(fullPath).startswith(('http://', 'https://'))
        
        if self.is_url:
            # For URLs, construct the job_info URL path similar to local logic
            print(f"Processing URL: {self.fullPath}")
            # 构造job_info URL: 从完整URL中去掉最后两级路径 (report/focus-ring/xxx.md) 然后添加 capx-job-info.json
            url_parts = str(self.fullPath).split('/')
            # 移除最后3部分: report, focus-ring, xxx.md
            base_url_parts = url_parts[:-3]
            job_info_url = '/'.join(base_url_parts) + '/capx-job-info.json'
            self.job_info = job_info_url
            print(f"Job info URL: {self.job_info}")
            self.imagePath = None
            self.rawResults = self.fullPath  # 保存URL路径，以便_getControlHistoryFromResult可以使用
        else:
            # For local paths, use existing logic
            self.job_info = Path(self.fullPath).parents[2] / "capx-job-info.json"
            print(f"Job info path: {self.job_info}")
            self.imagePath = Path("../../data/img/control")
            self.rawResults = Path(self.fullPath)
            
        self.osInfo = None
        self.versionInfo = None
        self.releaseVersion = "Unknown"  # Initialize with default value
        self.jiraVersion = None

        self.messageBot = MessageBot()

    def _readConfigs(self):
        if self.is_url:
            # For URLs, try to download the job_info from the constructed URL
            print("Processing URL - attempting to download job info")
            try:
                job_info_url = str(self.job_info)  # Ensure it's a string
                print(f"Downloading job info from: {job_info_url}")
                response = requests.get(job_info_url, timeout=30)
                if response.status_code == 200:
                    job_data = response.json()
                    self.osInfo = job_data.get("deviceOS", "Unknown")
                    self.versionInfo = job_data.get("appVersion", "0.0.0")
                    print(f"Successfully retrieved job info - OS: {self.osInfo}, Version: {self.versionInfo}")
                else:
                    print(f"Failed to download job info (status {response.status_code}), using default values")
                    self.osInfo = "Unknown"
                    self.versionInfo = "0.0.0"
            except Exception as e:
                print(f"Error downloading job_info from URL: {e}")
                self.osInfo = "Unknown"
                self.versionInfo = "0.0.0"
        elif self.job_info and Path(self.job_info).exists():
            try:
                with open(self.job_info, "r", encoding="utf-8") as f:
                    job_data = json.load(f)
                self.osInfo = job_data.get("deviceOS", "Unknown")
                self.versionInfo = job_data.get("appVersion", "0.0.0")
            except json.JSONDecodeError as e:
                print(f"Error reading job_info file: {e}")
                self.osInfo = "Unknown"
                self.versionInfo = "0.0.0"
        else:
            print(f"Job info file does not exist: {self.job_info}")
            # Set default values when job info doesn't exist
            self.osInfo = "Unknown"
            self.versionInfo = "0.0.0"

        if self.versionInfo is not None:
            affectVersion = self.versionInfo.split('.')
            if len(affectVersion) >=2:
                self.releaseVersion = ".".join(affectVersion[:2])
            else:
                self.releaseVersion = "Unknown"
        else:
            self.releaseVersion = "Unknown"
        
        self.jiraVersion = [{ "name": f'''WxRel-{self.releaseVersion}'''},]

    def _formatJiraTitle(self,row:pd.Series):
        osInfo = self.osInfo.split(" ")[0] if self.osInfo else "Unknown"
        title = f'''[Focus Ring][{osInfo}][{row["Description"]}][{row["Compliance"]}]'''
        if len(title) > 250:
            title = title[:250] + "..."
        
        return title
    
    
    def _formatJiraDescription(self,row:pd.Series, imageUrlMap = None):
        row = row.drop(labels=["Name Without Timestamp"], errors="ignore")
        columns = list(row.index)
        image_name = row.get("Image Name", "").strip()
        description = f'''h1. {{color:#172b4d}}WebEx APP Meetings Accessibility Report[{self.osInfo}][{self.versionInfo}]{{color}}\r\n\r\n'''
        description = description + "||" + "|| ".join(columns) + "||\r\n"
        rowReportStr = ""
        controlHistoryStr = ""
        if imageUrlMap is not None:
            print("imageUrlMap keys:", list(imageUrlMap.keys()), "imageUrlMap values:", list(imageUrlMap.values()))
        else:
            print("imageUrlMap is None")

        for index, value in row.items():
            if "Compliance" in index: # type: ignore
                value = f'''{{color:red}}{value}{{color}}'''

            if index == "Image":
                image_name = row.get("Image Name", "").strip()
                if imageUrlMap and image_name in imageUrlMap:
                    value = f'!{imageUrlMap[image_name]}|width=100!'
                
            rowReportStr = rowReportStr + " | " + value
        description += rowReportStr + " | \r\n\r\n"
            
        controlHistory = self._getControlHistoryFromResult(image_name)
        if controlHistory is not None and not controlHistory.empty:
            controlHistory = controlHistory.drop(columns=["Description", "Compliance"], errors='ignore')
            table_header = "|| " + " || ".join(controlHistory.columns) + " ||\r\n"
            table_rows = "\r\n".join(
                "| " + " | ".join(
                    f'!{imageUrlMap[row.get("Image Name", "").strip()]}|width=100!'
                    if col == "Image" and imageUrlMap and row.get("Image Name", "").strip() in imageUrlMap
                    else f"{{color:#FF0000}}*{val}*{{color}}" if idx == controlHistory.index[-2] and len(controlHistory) >= 2
                    else str(val)
                    for col, val in zip(controlHistory.columns, row)
                ) + " |"
                for idx, row in controlHistory.iterrows()
            )
            controlHistoryStr = f"h2. Control History\r\n{table_header}{table_rows}\r\n\r\n"
            description += controlHistoryStr

            return description
    
    def _getControlHistoryFromResult(self, imageName: str):
        if self.rawResults is None:
            return None
        df: pd.DataFrame = MarkdownToDataframe.MarkdownToDataframe(str(self.rawResults))

        if "Image" not in df.columns or df.empty:
            return None
        
        imageName = imageName.strip()
        progressImages = df["Image Name"].str.replace(r'.*[\\/]', '', regex=True).str.strip()
        matched_rows = df[progressImages == imageName]
        
        if matched_rows.empty:
            return None

        match_index = matched_rows.index[0]
        start_index = max(0, match_index - 5)
        end_index = min(len(df), match_index + 2)
        context_rows = df.iloc[start_index:end_index]

        return context_rows
        
    def _fileJiraBug(self,row:pd.Series):
        title = self._formatJiraTitle(row)
        descripiton = self._formatJiraDescription(row)
        jira = TeamsJiraIssueReporter(title,descripiton,self.jiraVersion)
        jira.labels.append("WRS_FocusRing")
        jiraID = jira.creatBug()
        title = title.replace("'", "\\'").replace("#!", "\\'")
        print(f'''Jira title: {title}''')
        print(f'''Jira description: {descripiton}''')

        if jiraID:
            imageName = row["Image Name"]
            print(f"Looking for history for image: {imageName}")
            historyDF = self._getControlHistoryFromResult(imageName)
            if historyDF is not None and "Image Name" in historyDF.columns:
                historyImages = historyDF["Image Name"].dropna().str.strip().unique()
                print(f"Found {len(historyImages)} history images: {list(historyImages)}")
            else:
                print("No history images found")
                historyImages = []

            img_html = str(row.get("Image", ""))
            print(f"Image HTML: {img_html}")
            match = re.search(r'src="([^"]+)"', img_html)
            rel_path = match.group(1).replace("\\", "/") if match else None
            print(f"Extracted rel_path: {rel_path}")
            
            if rel_path and not self.is_url:
                # 本地文件处理
                img_path = Path(self.fullPath.parents[0] / rel_path).parent.resolve()
                imagePaths = [
                        f"{img_path}/{name}"
                        for name in historyImages
                    ]
                uploadedUrls = jira.upload_image(jiraID, imagePaths)
                print(f"Upload result: {len(uploadedUrls) if uploadedUrls else 0} URLs uploaded")
                if uploadedUrls:
                    imageUrlMap = dict(zip(historyImages, uploadedUrls)) if uploadedUrls else {}
                    print(f"Created imageUrlMap with {len(imageUrlMap)} entries")
                    descripiton = self._formatJiraDescription(row, imageUrlMap)
                    jira.update_fields_for_issue(jiraID, {"description": descripiton})
            elif rel_path and self.is_url:
                # URL处理 - 构建绝对URL
                from urllib.parse import urljoin, urlparse
                base_url = str(self.fullPath).rsplit('/', 1)[0] + '/'  # 获取基础URL
                
                imagePaths = []
                for name in historyImages:
                    # 构建完整的图片URL
                    img_url = urljoin(base_url, rel_path + '/' + name)
                    imagePaths.append(img_url)
                
                print(f"Attempting to upload {len(imagePaths)} images from URLs")
                uploadedUrls = jira.upload_image(jiraID, imagePaths)
                print(f"URL upload result: {len(uploadedUrls) if uploadedUrls else 0} URLs uploaded")
                if uploadedUrls:
                    imageUrlMap = dict(zip(historyImages, uploadedUrls)) if uploadedUrls else {}
                    print(f"Created imageUrlMap with {len(imageUrlMap)} entries for URLs")
                    descripiton = self._formatJiraDescription(row, imageUrlMap)
                    jira.update_fields_for_issue(jiraID, {"description": descripiton})
                else:
                    print("No images were uploaded successfully")
            else:
                print(f"Warning: Could not extract image path from HTML: {img_html}")
                # 即使没有图片，也要有基本的描述
                descripiton = self._formatJiraDescription(row, None)
                if descripiton:
                    jira.update_fields_for_issue(jiraID, {"description": descripiton})
        return (jiraID,title)

    def FileNewJiraNotifition(self,JiraInfos):
        print("ready to File New Jira Notifition....")
        if len(JiraInfos) == 0:
            return
        
        message = "#### **New Focus Ring Issue(s) found:**\n"
        for jiraInfo in JiraInfos:
            jiraID = jiraInfo[0]
            title = jiraInfo[1]
            newLine = f'''* **[{jiraID}](https://jira-eng-gpk2.capx.com/jira/browse/{jiraID})** [{title}]\n'''
            message = message + newLine
        
        message = message + f'''* **[More ... ](https://jira-eng-gpk2.capx.com/jira/secure/Dashboard.jspa?selectPageId=61721)**'''
        self.messageBot.sendMessageToTeams(message)

    def ParserReportAndFileBugs(self):
        try:
            print("Starting ParserReportAndFileBugs")
            self._readConfigs()
            print(f"Reading report from: {self.fullPath}")
            
            df:pd.DataFrame = MarkdownToDataframe.MarkdownToDataframe(self.fullPath)
            
            print(f"Parsed DataFrame shape: {df.shape}")
            if not df.empty:
                print(f"Available columns: {df.columns.tolist()}")
                print("First 5 Image Names:")
                for i, name in enumerate(df["Image Name"].head().tolist()):
                    print(f"  {i+1}: '{name}'")
            else:
                print("DataFrame is empty after parsing")
                return {"success": False, "message": "No data found in report", "jira_ids": []}
            
            print(f"Looking for image: '{self.itemName.strip()}'")
            
            # 只进行精确匹配，不允许部分匹配
            df = df[df["Image Name"].str.strip() == self.itemName.strip()]
            if df.empty:
                print(f"No exact match found for image: {self.itemName}")
                return {"success": False, "message": f"No exact match found for image: {self.itemName}", "jira_ids": []}
            
            df.reset_index(drop=True, inplace=True)
            print(f"Processing {len(df)} matching rows")
            jiraInfos = []

            df["Name Without Timestamp"] = df["Image Name"].apply(lambda x: x.split("_", 1)[-1])
            for idx, (index, row) in enumerate(df.iterrows()):
                print(f"Processing row {idx + 1}/{len(df)}: {row['Image Name']}")
                
                try:
                    hashString = f"{row['Description']}|{row['Name Without Timestamp']}"
                    IssueHash = hashlib.sha256(hashString.encode("utf-8")).hexdigest()
                    sql = f'''select * from `RegressShield`.`bugInfo` where `hash` = "{IssueHash}" or `hashString` = "{hashString}";'''
                    
                    print(f"Checking for duplicates with hash: {IssueHash}")
                    results,_ = self.dbconnection.Query(sql)
                    
                    if len(results) > 0:
                        message = f'''FocusRing: duplicate issue with hash:{IssueHash}, hashString:{hashString}'''
                        print(message)
                        continue
                    
                    print("Creating JIRA issue...")
                    jiraID,title = self._fileJiraBug(row)
                    
                    if jiraID is not None:
                        print(f'''New focus ring bug: https://jira-eng-gpk2.capx.com/jira/browse/{jiraID}''')
                        date = datetime.today().date()
                        sql1 = f'''INSERT INTO `RegressShield`.`bugInfo` (`jiraID`, `createDate`, `title`, `affectVersion`, `platform`, `hash`, `hashString`, `status`) VALUES ('{jiraID}', '{str(date)}', '{title}', '{self.releaseVersion}', '{self.osInfo}', '{IssueHash}', '{hashString}', 'open');'''
                        self.dbconnection.Execute(sql1)
                        jiraInfos.append((jiraID,title))
                    else:
                        print("Failed to create JIRA issue")
                        
                except Exception as row_error:
                    logger.error(f"Error processing row {idx + 1}: {str(row_error)}")
                    logger.error(f"Row data: {row}")
                    continue

            print(f"Sending notifications for {len(jiraInfos)} new issues")
            self.FileNewJiraNotifition(jiraInfos)
            
        except Exception as e:
            logger.error(f"Error in ParserReportAndFileBugs: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "message": f"Error processing report: {str(e)}", "jira_ids": []}
        
        # Return result with JIRA IDs
        jira_ids = [info[0] for info in jiraInfos]
        print(f"Completed processing. Created {len(jira_ids)} new issues")
        return {
            "success": True, 
            "message": f"Processed {len(jiraInfos)} new issues", 
            "jira_ids": jira_ids,
            "jira_details": [{"id": info[0], "title": info[1]} for info in jiraInfos]
        }

    def AddJiaInfoAndToHTML(self,htmlPath):
        df:pd.DataFrame = MarkdownToDataframe.MarkdownToDataframe(self.fullPath)
        df["References"] = df["References"].str.replace("**","")
        df["Jira"] = ""
        for index,row in df.iterrows():
            description = row["Description"]
            sql = f'''SELECT jiraID FROM RegressShield.bugInfo where hashString = "{description}";'''
            data,_ = self.dbconnection.Query(sql)
            df.at[index, 'References'] = f'''<b>{row["References"]}</b>'''

            if len(data) >0:
                df.at[index, 'Jira'] = f'''<a href="https://jira-eng-gpk2.capx.com/jira/browse/{data[0][0]}" target="_blank">{data[0][0]}</a>''' 
    
        MarkdownToDataframe.DataframeToHTML(df,htmlPath)


class TeamsJiraIssueReporter(object):
    def __init__(self,summary,description,affectsVersions = None, fixversions = None):
        self.summary = summary
        self.description = description
        self.components = [{"name": "Client: Desktop (Windows and MacOS)"},]
        self.issuetype = {"name": "Bug"}
        self.epicLink = "SPARK-559755"
        self.project = {"key": "SPARK"}
        self.affectsVersions = affectsVersions #[{ "name": "WBS41.7.0"},]
        self.watchers = [] 
        self.Team = {"value": "Polaris"}
        self.found = { "value":"Test" }
        self.labels = ["CapabilityX",]
        self.assignee = {"name":"binbiwan"}
        self.severity = {"value": "S3 - Moderate"}
        self.priority = {'name': "P3"}
        self.fixVersions = fixversions
        self.JIRA_token = JIRA_token

    def __formatBugPayload(self):
        payload = {}
        if self.summary is None:
            return None

        if self.description is None:
            return None

        payload['summary'] = self.summary
        payload['description'] = self.description
        payload['issuetype'] = self.issuetype
        payload['project'] = self.project
        payload['components'] = self.components
        payload['customfield_10712'] = self.found
        payload['customfield_10408'] = self.severity
        payload['priority'] = self.priority
        if self.epicLink is not None:
            payload['customfield_10001'] = self.epicLink
        if self.affectsVersions is not None:
            payload['versions'] = self.affectsVersions
        if self.fixVersions is not None:
            payload['fixVersions'] = self.fixVersions
        payload['customfield_11800'] = self.Team
        if self.labels is not None:
            payload['labels'] = self.labels

        if self.assignee is not None:
            payload['assignee'] = self.assignee
            
        return {"fields":payload}

    def __formatTaskPayload(self):
        payload = {}
        if self.summary is None:
            return None

        if self.description is None:
            return None

        payload['summary'] = self.summary
        payload['description'] = self.description
        payload['issuetype'] = {"name": "Task"}
        payload['project'] = self.project
        payload['components'] = self.components
        if self.epicLink is not None:
            payload['customfield_10001'] = self.epicLink
        payload['customfield_11800'] = self.Team
        if self.labels is not None:
            payload['labels'] = self.labels

        if self.assignee is not None:
            payload['assignee'] = self.assignee

        return {"fields": payload}

    def sendCreateIssueRequest(self,payload):
        url = "https://jira-eng-gpk2.capx.com/jira/rest/api/2/issue/"

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.JIRA_token} "
        }
        request_payload = json.dumps(payload)

        print(request_payload)
        response = requests.request(
            "POST",
            url,
            data=request_payload,
            headers=headers,
        )

        if response.status_code == 201:
            print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
            jiraID = json.loads(response.text)['key']
            return jiraID
        else:
            print(response,response.status_code,response.text)
            return None

    
    def ModifyWatcher(self,JiraID,watcher):
        J = JIRA(server='https://jira-eng-gpk2.capx.com/jira', token_auth=self.JIRA_token)
        J.add_watcher(JiraID,watcher)

    def update_reporter(self, JiraID, reporter="binbiwan"):
        jira_url = 'https://jira-eng-gpk2.capx.com/jira'
        jira = JIRA(server=jira_url, token_auth=JIRA_token)
        issue = jira.issue(JiraID)
        fields = {}
        fields['reporter'] = {'name': reporter}
        try:
            issue.update(fields)
        except Exception as e:
            print(f"reporter has no jira access: {JiraID}: {e}")

    def update_fields_for_issue(self,issue_id, field):
        jira_url = 'https://jira-eng-gpk2.capx.com/jira'
        jira = JIRA(server=jira_url, token_auth=JIRA_token)
        try:
            issue = jira.issue(issue_id)
            issue.update(fields=field)
            return f'Successfully updated JIRA issue {issue_id}'
        except Exception as e:
            error_message = f'Failed to update JIRA issue {issue_id}: {e}'
            return error_message

    def creatTask(self):
        payload = self.__formatTaskPayload()
        JiraID = self.sendCreateIssueRequest(payload)
        if JiraID != None:
            for watcher in self.watchers:
                self.ModifyWatcher(JiraID, watcher)
            self.update_reporter(JiraID)
        return JiraID

    def creatBug(self):
        payload = self.__formatBugPayload()
        JiraID = self.sendCreateIssueRequest(payload)
        if JiraID !=None:
            print(f'''New Jira Created: https://jira-eng-gpk2.capx.com/jira/browse/{JiraID}''')
            for watcher in self.watchers:
                self.ModifyWatcher(JiraID,watcher)
            self.update_reporter(JiraID)
        return JiraID
    
    def upload_image(self, issue_key, image_paths):
        headers = {
            "Authorization": AUTHORIZATION,
            "X-Atlassian-Token": "no-check"
        }
        url = f"https://jira-eng-gpk2.capx.com/jira/rest/api/2/issue/{issue_key}/attachments"
        files = []
        try:
            for image_path in image_paths:
                mime_type = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
                files.append(("file", (image_path, open(image_path, "rb"), mime_type)))

            response = requests.post(url, headers=headers, files=files)

            if response.status_code == 200:
                response_data = response.json()
                uploaded_urls = [attachment["content"] for attachment in response_data]
                print("File upload success")
            else:
                print(f"File upload failed: {response.status_code}, {response.text}")
        finally:
            for _, file_tuple in files:
                file_tuple[1].close()
        return uploaded_urls

    def delete_attachment(self, attachment_id):
        url = f"https://jira-eng-gpk2.capx.com/jira/rest/api/2/attachment/{attachment_id}"
        headers = {
            "Authorization": AUTHORIZATION
        }
        response = requests.delete(url, headers=headers)
        if response.status_code == 204:
            print(f"Attachment {attachment_id} deleted successfully.")
        else:
            print(f"Failed to delete attachment {attachment_id}: {response.status_code}, {response.text}")

    @staticmethod
    def AddComments(jiraID,comments):
        J = JIRA(server='https://jira-eng-gpk2.capx.com/jira', token_auth=JIRA_token)
        J.add_comment(jiraID, comments)

    @staticmethod
    def Search(jql):
        url = f'''https://jira-eng-gpk2.capx.com/jira/rest/api/2/search?{jql}'''

        headers = {
            "Content-Type": "application/json",
            "Authorization":AUTHORIZATION
        }
        response = requests.request(
            "GET",
            url,
            headers=headers,
        )
        js = json.loads(response.text)
        issues = js["issues"]
        JiraIDs = []
        for issue in issues:
            JiraIDs.append(issue["key"])

        return JiraIDs
    
    @staticmethod
    def FilterAndUpdateTeamPT():
        jql = f'''jql=labels%20%3D%20CapabilityX%20and%20"Epic%20Link"%20%3DSPARK-559755%20and%20"Team%2FPT"%20not%20in%20(Polaris)'''
        JiraIDs = TeamsJiraIssueReporter.Search(jql)
        for jiraID in JiraIDs:
            jira = TeamsJiraIssueReporter(None,None)
            fields = {}
            fields['reporter'] = {'name': "binbiwan"}
            fields['customfield_11800'] = {"value": "Polaris"}
            jira.update_fields_for_issue(jiraID,fields)
            print(f'''update: https://jira-eng-gpk2.capx.com/jira/browse/{jiraID} to Polaris''')
#================================================================================================================================

class MysqlConnection(object):
    def __init__(self,host, port, user, password, dbName, charset = 'utf8mb4'):
        self.db = pymysql.connect(host= host, port=port,user=user, password=password,db=dbName, charset=charset)

    def __del__(self):
        if self.db:
            self.db.close()


    def Query(self,sql_statement):
        if self.db is None:
            return ((),())

        try:
            self.db.ping(reconnect=True)
        except Exception as e:
            logger.error(f"Database reconnect failed: {e}")
            return ((),())

        cursor = self.db.cursor()
        try:
            cursor.execute(sql_statement)
            results = cursor.fetchall()
            columns = [item[0] for item in cursor.description]
            return (results,columns)
        except Exception as e:
            print(f"Error: unable to fetch data: {e}", "RED")
            logger.error(f"Query failed: {e} | SQL: {sql_statement}")
        
        return ((),())
        
    def Execute(self,sql_statement):
        if self.db is None:
            print('Execute failed, db is None',"RED")
            return False

        cursor = self.db.cursor()
        try:
            cursor.execute(sql_statement)
            self.db.commit()
            return True
        except Exception as e:
            msg = f'''Execute failed!,sql[{sql_statement}], error{e}'''
            print(msg,"RED")
            self.db.rollback()
            return False
        
    def ExecuteWithData(self, sql_statement, data):
        if self.db is None:
            print('Execute failed, db is None',"RED")
            return False

        cursor = self.db.cursor()
        try:
            cursor.execute(sql_statement, data)
            self.db.commit()
            return True
        except Exception as e:
            msg = f'''Execute failed!,sql[{sql_statement}], error{e}'''
            print(msg,"RED")
            self.db.rollback()
            return False
            
    def TableInfo(self):
        if self.db is None:
            return None
        cursor = self.db.cursor()
        columns = [item[0] for item in cursor.description]
        return columns
    
class MessageBot(object):
    def __init__(self):
        self.bear_token = "NWE0ZjBhZjEtNDUxZS00ZDNkLThhOGItMjcwNjUwMjFlNWZkMDI2NTY0MmQtY2Nl_PF84_1eb65fdf-9643-417f-9974-ad72cae0e10f"

    def sendMessageToTeams(self,message,roomId ="c0af0ac0-772f-11ef-9431-6382b932281b"):    
        if roomId is None:
            return 
        sparkapi = 'https://api.capxspark.com/v1/messages'
        headers = {
                'Content-Type': 'application/json;charset=UTF-8',
                'Authorization': f'''Bearer {self.bear_token}'''
                }
        data = {"roomId": roomId, "text": "", "markdown": "%s" % (message)}
        try:
            req = requests.post(sparkapi, data=json.dumps(data), headers = headers)
            if req.status_code == 200:
                print(f"Notify message bot succeeded. with room ID: ({roomId})")
            else:
                print(f"Notify message bot failed, status code : {req.status_code} - {req.text} with room ID: {roomId}")
        except Exception as e:
            print(f"Notify message bot failed")

    def sendMessageToPerson(self,emailaddress, message): 
        if emailaddress is None:
            return
        sparkapi = 'https://api.capxspark.com/v1/messages'
        headers = {
                'Content-Type': 'application/json;charset=UTF-8',
                'Authorization': f'''Bearer {self.bear_token}'''
                }
        data = {"toPersonEmail": emailaddress, "text": "", "markdown": "%s" % (message)}
        try:
            req = requests.post(sparkapi, data=json.dumps(data), headers = headers)
            if req.status_code == 200:
                print(f"Notify message bot succeeded. with person email: ({emailaddress})")
            else:
                print(f"Notify message bot failed, status code : {req.status_code} - {req.text} with person email: {emailaddress}")
        except Exception as e:
            print(f"Notify message bot failed: {e}")

    def sendCardToTeams(self,card_content, roomId="c0af0ac0-772f-11ef-9431-6382b932281b"):
        if roomId is None:
            return
            
        sparkapi = 'https://api.capxspark.com/v1/messages'
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'''Bearer {self.bear_token}'''
        }
        
        data = {
            "roomId": roomId,
            "text": "Test Execution Report - please update your client to see the full card",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card_content
            }]
        }
        
        try:
            req = requests.post(sparkapi, data=json.dumps(data), headers=headers)
            if req.status_code == 200:
                print(f"Notify card message bot succeeded. with room ID: ({roomId})")
                return True
            else:
                print(f"Notify card message bot failed, status code : {req.status_code} - {req.text} with room ID: {roomId}")
                return False
        except Exception as e:
            print(f"Notify card message bot failed: {e}")
            return False

    def sendCardToPerson(self,emailaddress, card_content):
        if emailaddress is None:
            return
            
        sparkapi = 'https://api.capxspark.com/v1/messages'
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Authorization': f'''Bearer {self.bear_token}'''
        }
        
        data = {
            "toPersonEmail": emailaddress,
            "text": "Test Execution Report - please update your client to see the full card",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card_content
            }]
        }
        
        try:
            req = requests.post(sparkapi, data=json.dumps(data), headers=headers)
            if req.status_code == 200:
                print(f"Notify card message bot succeeded. with person email: ({emailaddress})")
                return True
            else:
                print(f"Notify card message bot failed, status code : {req.status_code} - {req.text} with person email: {emailaddress}")
                return False
        except Exception as e:
            print(f"Notify card message bot failed: {e}")
            return False
        
class MarkdownToDataframe(object):
    def __init__(self) -> None:
        pass

    @staticmethod
    def MarkdownToDataframe(path, startLine=0) -> pd.DataFrame:
        from io import StringIO
        
        # Check if path is URL or local file
        if str(path).startswith(('http://', 'https://')):
            # Handle URL
            try:
                import requests
                # 增加超时时间并添加重试机制
                session = requests.Session()
                session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                # 先尝试较短的超时时间，然后递增
                timeout_values = [30, 60, 90]
                content = None
                
                for timeout in timeout_values:
                    try:
                        print(f"Attempting to download URL with {timeout}s timeout...")
                        response = session.get(path, timeout=timeout)
                        response.raise_for_status()
                        content = response.text
                        print(f"Successfully downloaded content from URL: {path}")
                        break
                    except requests.exceptions.Timeout:
                        print(f"Timeout with {timeout}s, trying next...")
                        continue
                
                if content is None:
                    print(f"All timeout attempts failed for URL {path}")
                    return pd.DataFrame()
                
                # Check if content is HTML (contains table tags)
                print(f"Content length: {len(content)} characters")
                print(f"Contains table tag: {'<table' in content.lower()}")
                
                data_label_check = 'data-label="image name"' in content.lower()
                print(f"Contains data-label: {data_label_check}")
                
                if '<table' in content.lower() and data_label_check:
                    return MarkdownToDataframe._parse_html_table(content)
                else:
                    print("Content does not appear to be HTML table format, trying markdown parsing...")
                    # 可能是markdown格式，继续用原来的逻辑处理
                
            except requests.exceptions.Timeout:
                print(f"Final timeout occurred while downloading from URL {path}")
                return pd.DataFrame()
            except requests.exceptions.ConnectionError:
                print(f"Connection error while downloading from URL {path}")
                return pd.DataFrame()
            except requests.RequestException as e:
                print(f"Failed to download from URL {path}: {e}")
                return pd.DataFrame()
        else:
            # Handle local file
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except FileNotFoundError as e:
                logger.error(f"File not found: {path}")
                return pd.DataFrame()  # Return empty DataFrame on error
        
        # Process the content as markdown (same logic for both URL and file)
        csv_data = "\n".join(line.strip('| ') for line in content.strip().split('\n')[startLine:])
        data = StringIO(csv_data)
        tmpDf = pd.read_csv(data, sep="|")
        tmpDf.columns = tmpDf.columns.str.strip()
        df = pd.DataFrame(tmpDf[1:])
        df.reset_index(drop=True, inplace=True)
        return df
    
    @staticmethod
    def _parse_html_table(html_content):
        """
        解析HTML表格并转换为DataFrame
        """
        import re
        
        try:
            # 使用正则表达式提取表格数据，支持多行内容
            data = []
            
            # 改进的正则表达式模式，支持多行和复杂内容
            # 使用DOTALL标志让.匹配换行符
            image_pattern = r'<td data-label="Image Name"[^>]*>(.*?)</td>'
            desc_pattern = r'<td data-label="Description"[^>]*>(.*?)</td>'
            comp_pattern = r'<td data-label="Compliance"[^>]*>(.*?)</td>'
            comment_pattern = r'<td data-label="Comment"[^>]*>(.*?)</td>'
            image_cell_pattern = r'<td data-label="Image"[^>]*>(.*?)</td>'
            
            # 查找所有匹配的数据
            image_matches = re.findall(image_pattern, html_content, re.DOTALL)
            desc_matches = re.findall(desc_pattern, html_content, re.DOTALL)
            comp_matches = re.findall(comp_pattern, html_content, re.DOTALL)
            comment_matches = re.findall(comment_pattern, html_content, re.DOTALL)
            image_cell_matches = re.findall(image_cell_pattern, html_content, re.DOTALL)
            
            print(f"Found {len(image_matches)} image names, {len(desc_matches)} descriptions, {len(comp_matches)} compliance entries")
            
            # 确保所有列表长度相同
            min_length = min(len(image_matches), len(desc_matches), len(comp_matches))
            
            for i in range(min_length):
                # 清理文本，移除HTML标签和多余空白
                image_name = re.sub(r'<[^>]+>', '', image_matches[i]).strip()
                description = re.sub(r'<[^>]+>', '', desc_matches[i]).strip()
                compliance = re.sub(r'<[^>]+>', '', comp_matches[i]).strip()
                comment = re.sub(r'<[^>]+>', '', comment_matches[i]).strip() if i < len(comment_matches) else ""
                
                # 尝试从img标签的alt属性获取完整文件名
                full_image_name = image_name
                if i < len(image_cell_matches):
                    img_html = image_cell_matches[i]
                    # 查找alt属性中的完整文件名
                    alt_match = re.search(r'alt="([^"]*)"', img_html)
                    if alt_match:
                        alt_name = alt_match.group(1).strip()
                        # 清理alt名称，移除可能的HTML属性片段
                        alt_name = alt_name.split('"')[0].strip()
                        if alt_name and alt_name.endswith('.png'):
                            full_image_name = alt_name
                            #print(f"Found full name in alt: {alt_name} (was: {image_name})")
                    
                    # 也尝试从src属性获取文件名
                    src_match = re.search(r'src="[^"]*[/\\]([^/\\]*)"', img_html)
                    if src_match:
                        src_name = src_match.group(1).strip()
                        if src_name and src_name.endswith('.png') and len(src_name) > len(full_image_name):
                            full_image_name = src_name
                            #print(f"Found full name in src: {src_name} (was: {full_image_name})")
                
                # 清理Unicode字符和特殊符号（但保留文件名中的常见字符）
                full_image_name = re.sub(r'[^\w\s\.-]', '', full_image_name)
                description = re.sub(r'[^\w\s\.-]', '', description)
                compliance = re.sub(r'[^\w\s\.-]', '', compliance)
                
                if full_image_name and description:  # 确保不是空行
                    data.append({
                        'Image Name': full_image_name,
                        'Description': description,
                        'Compliance': compliance,
                        'Comment': comment,
                        'Image': image_cell_matches[i] if i < len(image_cell_matches) else ""
                    })
                   # print(f"Added row: {full_image_name} - {compliance}")
            
            df = pd.DataFrame(data)
            print(f"Successfully parsed {len(df)} rows from HTML table")
            
            # 调试输出：显示前几行数据
            if not df.empty:
                print("Sample data:")
                print(df.head()[['Image Name', 'Compliance']].to_string())
            
            return df
            
        except Exception as e:
            print(f"Error parsing HTML table: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return pd.DataFrame()
    

    @staticmethod 
    def DataframeToHTML(df:pd.DataFrame,htmlPath):
        html = df.to_html(escape=False,index=False)
        styled_html = ""
        if len(html) != 0:
            styled_html = f"""
            <!DOCTYPE html> <html lang="zh">
            <head> <meta charset="UTF-8"> <style> 
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid black; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    tr:nth-child(odd) {{ background-color: #ffffff; }}
                    </style>
            </head> 
            <body> {html} </body>
            </html>
            """
            with open(htmlPath,"w+",encoding="utf-8",errors="ignore") as f:
                f.write(styled_html)


if __name__ == "__main__":
    fullPath = Path("/Users/weiqli/Downloads/20250729-094151/report/focus-ring/test.md")
    itemName = f'20250729094307_More_options.png'
    jira = ReportParserToJira(fullPath,itemName)
    jira.ParserReportAndFileBugs()