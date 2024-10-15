from openai import AzureOpenAI
import os
import time
import dotenv
import random
import chainlit as cl
import asyncio
import sys
import datetime
import csv


global thread_id
global assistant_id


dotenv.load_dotenv()

count=0

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-05-01-preview", # 執筆時点ではこのバージョンのみ対応
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
)

#ファイル送信
my_file = client.files.create(
  file=open("DB.csv", "rb"),
  purpose="assistants"
)
file_id = my_file.id

#Assistant 作成する関数
def assistant_fun(file_id):

    #systemprompt.txtを読み込ませる
    with open("./system_prompt.txt","r",encoding="utf-8") as file:
        instructions = file.read()

    my_assistant = client.beta.assistants.create(
        name="secretary",
        instructions=instructions,
        tools=[{"type": "code_interpreter"}],
        model="gpt-4o",
        tool_resources={"code_interpreter": {"file_ids": [file_id]}}
        )

    assistant_id = my_assistant.id
    return assistant_id



# スレッドの生成する関数
def create_thread_fun():
    thread = client.beta.threads.create()
    thread_id = thread.id
    return thread_id


#Messageを追加する関数
#ユーザーからのメッセージをスレッドに追加
def user_message_fun(user_message, thread_id):

    # スレッドに紐づけたメッセージの生成
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message
    )
    return message


#THreadを実行する関数
def run_fun(thread_id, assistant_id):
        time.sleep(random.uniform(10, 15))  # ランダムな遅延を挿入
        #print("{Running run_fun...}")#debug
        run = client.beta.threads.runs.create(
            assistant_id=assistant_id,
            thread_id=thread_id
        )

        return run


# アシスタントが回答のメッセージを返すまで待つ関数
def wait_for_assistant_response(thread_id, run_id):
    max_retries = 5  # 最大リトライ回数
    retry_count = 0  # リトライカウンター

    while retry_count < max_retries:
        time.sleep(random.uniform(3, 5))  # 60秒から90秒のランダムな間隔で待機する
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run_id
        )
        #print("{Run status:", run.status, "}") #debug

        status = run.status
        if status in ["completed", "cancelled", "expired", "failed"]:
            if status == "failed":
                #print("{Run failed at:", run.failed_at, "}")#debug
                #print("{Error details:", run.last_error, "}")#debug
                if "rate_limit_exceeded" in run.last_error.message:
                    wait_time = int(run.last_error.message.split("Try again in ")[1].split(" seconds.")[0])
                    time.sleep(wait_time + 5)  # 待機時間に20秒追加してからリトライ
                    retry_count += 1
                    continue  # リトライ
            #print("{", status, "}")#debug
            break

        retry_count += 1

    if retry_count == max_retries:
        print("最大リトライ回数に達しました。処理を中止します。")


#スレッドのメッセージを確認する関数
def print_thread_messages(thread_id):

    msgs = client.beta.threads.messages.list(thread_id=thread_id)
    for m in msgs:
        assert m.content[0].type == "text"
        message = f"tourist_assistant: {msgs.data[0].content[0].text.value}"

        return message
    
 # ファイル等の削除
def dele(file_id,assistant_id,thread_id):
   
    client.files.delete(file_id=file_id)  # ファイルの削除
    client.beta.assistants.delete(assistant_id)  # アシスタントの削除
    client.beta.threads.delete(thread_id=thread_id)  # スレッドの削除

            
#スレッドをテキストに書き出す
def write_messages_to_file(thread_id, filename="thread_messages.txt"):
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    with open(filename, "a", encoding="utf-8") as file:
        for message in messages.data:
            file.write(f"{message.role}: {message.content}\n")

#ファイルの中身を初期化する
def init_file(filename="thread_messages.txt"):
    # 'w'モードでファイルを開くことで初期化
    with open(filename, 'w') as f:
        # 必要に応じて初期行を追加することも可能
        # f.write("初期行のテキスト\n")  # 初期行を追加したい場合
        pass  # 何も書き込まない場合はpassを使う

#全スレッドをコピーする
def convert_text_to_csv(input_filename="thread_messages.txt"):

    now = datetime.datetime.now()
    csv_filename = './output/log_' + now.strftime('%Y%m%d_%H%M%S') + '.csv'

    # テキストファイルを読み込み
    with open(input_filename, 'r', encoding='utf-8') as text_file:
        lines = text_file.readlines()
        
    # CSVファイルに書き込み
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        
        for line in lines:
            # 行をカンマで分割（必要に応じて区切り文字を変更）
            row = line.strip().split(',')  # カンマで区切る
            writer.writerow(row)


assistant_id = assistant_fun(file_id)
thread_id = create_thread_fun()
init_file()


# チャットが開始されたときに実行される関数
@cl.on_chat_start
async def on_chat_start():
    await cl.Message(content="行きたい観光地を紹介します。(qを入力すれば終了)\n1つずつ内容の入力お願いします。\n同じ言葉が返ってきたら再び入力お願いします。\nあなたのいる場所を入力してください（例：八王子駅）").send() # 初期表示されるメッセージを送信する

# メッセージが送信されたときに実行される関数
@cl.on_message 
async def on_message(input_message):
    print("入力されたメッセージ: " + input_message.content)
    
    if input_message.content!="終了":

        # ユーザーのメッセージを文字列として取得
        user_message = input_message.content  # ここで content プロパティを使用してメッセージ内容を取得

        # ユーザーのメッセージを作成する
        user_message_fun(user_message, thread_id)
        # スレッドの実行
        run = run_fun(thread_id, assistant_id)
        # 結果待ち
        wait_for_assistant_response(thread_id, run.id)
        # 結果確認
        message = print_thread_messages(thread_id)
        # スレッドメッセージを追加
        write_messages_to_file(thread_id)
        
        await cl.Message(content=message).send()  # チャットボットからの返答を送信する

    else:
        message = input_message.content
        print("チャットを終了します")
        convert_text_to_csv()
        dele(file_id, assistant_id,thread_id)
        await cl.Message(content="ご利用ありがとうございました。これ以降の入力は絶対にやめるようにお願いいたします。").send() # チャットボットからの返答を送信する
        # 画像ファイルのパス
        image_path = "./image/end.png"
    
        # 画像を読み込み、チャットボットのメッセージとして表示
        image = cl.Image(path="./image/end.jpeg", name="image1", display="inline")
        # 画像を読み込み、チャットボットのメッセージとして表示
        await cl.Message(content= "表示したい画像の説明",elements=[image]).send()

        @cl.on_message
        async def on_message(message: cl.Message):
            response = "終了しました。画面を閉じるようにお願いします。"
            await cl.Message(response).send()


