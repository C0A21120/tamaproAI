from openai import AzureOpenAI
import os
import time
import dotenv
import random

dotenv.load_dotenv()

count=0

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-05-01-preview", # 執筆時点ではこのバージョンのみ対応
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
)

#ファイル送信
my_file = client.files.create(
  file=open("touristspot.txt", "rb"),
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
        model="ssdl-gpt-4o",
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
        time.sleep(random.uniform(5, 8))  # ランダムな遅延を挿入
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
        time.sleep(random.uniform(3, 10))  # 60秒から90秒のランダムな間隔で待機する
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
    with open(filename, "w", encoding="utf-8") as file:
        for message in messages.data:
            file.write(f"{message.role}: {message.content}\n")
            





def main():
    #ユーザーの詳細設定を聞くAI
    response="""
    ユーザーの情報を聞くオペレーターとしてふるまってください。
    ユーザーと対話して、観光地をお勧めするのに必要な情報を集める必要があります。
    観光地をお勧めするために必要となるのは、
    １，現在地 - 今現在いる駅や観光地,
    ２，年齢 - 何歳,
    ３，旅行経験 - 旅行経験はどのくらいか,
    ４，予算 - 何円ほど使えるか,
    ５，旅行の頻度 - 旅行をする頻度はどのくらいか,
    ６，市内での移動手段 - 市内での移動方法は電車か車かそれ以外か,
    です。
    ユーザーへは必要な情報を1つずつ問い合わせて、対話的に回答を引き出してください。
    すべての情報が集まったら、以下のJson形式で出力してください。必ず、マークダウン記法で出力してください。
    '''json
    {
        "Current location":現在地,
        "Age":年齢,
        "Travel experience":旅行経験,
        "Budget":予算,
        "Frequency of travel":旅行の頻度,
        "Means of transportation within the city":市内での移動手段,

    }
    '''
    ユーザーへの最初の質問を開始してください。ユーザーが回答したら次の質問に移ってください。
    最後の出力に「これらの情報を用いてお客様に最適な観光地を提供してください。」と入れてください。
    """
    #model_version() #モデルのバージョン確認
    assistant_id = assistant_fun(file_id)
    thread_id = create_thread_fun()

    #ユーザーの詳細設定を聞くAI
   # LLMの役割を定義
    conversation = [{"role":"system","content":response}]

    conversation.append({"role": "user", "content": "最初の質問をお願いします"})
    # Azure OpenAIにリクエストを送信 
    response = client.chat.completions.create(
    model="ssdl-gpt-4o",
    messages=conversation,
    )
    conversation.append({"role":"assistant","content":response.choices[0].message.content})
    print("AI:",response.choices[0].message.content + "\n")

    for i in range(6):
        user_input = input("user:")
        conversation.append({"role": "user", "content": user_input})

            # Azure OpenAIにリクエストを送信 
        response = client.chat.completions.create(
        model="ssdl-gpt-4o",
        messages=conversation,
        )
        conversation.append({"role":"assistant","content":response.choices[0].message.content})
        if i !=5 :
            print("AI:",response.choices[0].message.content + "\n")
        else:
            print("情報が集まりました。少々お待ちください")
            user_message=response.choices[0].message.content
    



    #チャットボット開始

    #ユーザーのメッセージを作成する
    user_message_fun(user_message, thread_id)

        # スレッドの実行
    run = run_fun(thread_id, assistant_id)

        #結果待ち
    wait_for_assistant_response(thread_id, run.id)
        
        #結果確認
    message = print_thread_messages(thread_id)
    print(message)
        
        #メッセージをテキストに入力
    write_messages_to_file(thread_id)

    while True:
        count=0
        user_message = input("user(\"q\" push to end):")

        if user_message == "q":
            print("チャットを終了します")
            write_messages_to_file(thread_id)
            dele(file_id, assistant_id,thread_id)
            break

    
        #ユーザーのメッセージを作成する
        user_message_fun(user_message, thread_id)

        # スレッドの実行
        run = run_fun(thread_id, assistant_id)

        #結果待ち
        wait_for_assistant_response(thread_id, run.id)
        
        #結果確認
        message = print_thread_messages(thread_id)
        print(message)
        
        #メッセージをテキストに入力
        write_messages_to_file(thread_id)

        count+=1


if __name__ == "__main__":
    main()



