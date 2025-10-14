import MeCab
import random
import configparser
import sys
import os
from collections import defaultdict

def parse_text_to_words(tagger, text):
    """MeCabを使って文章を単語のリストに分割する"""
    node = tagger.parseToNode(text)
    words = []
    while node:
        word = node.surface
        if word and node.posid != 0: # MeCab自身のBOS/EOSノードはスキップ
            words.append(word)
        node = node.next
    return words

def create_triplets_from_words(words):
    """単語リストからマルコフ連鎖用の3単語の組を作成する（BOS/EOSトークンを含む）"""
    if len(words) < 2:
        return []
    
    # この関数内でBOS/EOSトークンを追加する
    tokens = ["@BOS@"] + words + ["@EOS@"]
    
    triplets = []
    for i in range(len(tokens) - 2):
        w1, w2, w3 = tokens[i], tokens[i+1], tokens[i+2]
        triplets.append((w1, w2, w3))
        
    return triplets

def create_config_template(config_path):
    """設定ファイルのテンプレートを生成する"""
    config = configparser.ConfigParser()
    config['Files'] = {
        'response_path': 'response.txt',
        'content_path': 'content.txt',
        'transition_path': 'transition.txt',
        'output_wordlist_path': 'MarkovWordList.txt',
        'output_intdict_path': 'MarkovIntDictionary.txt'
    }
    config['Settings'] = {
        'combinations': '5000'
    }
    with open(config_path, 'w', encoding='utf-8') as f:
        config.write(f)
    print(f"設定ファイル '{config_path}' が見つからなかったため、テンプレートを生成しました。")
    print("ファイルパスなどを編集してから、再度スクリプトを実行してください。")

def main():
    config_path = 'config.ini'
    config = configparser.ConfigParser()

    if not os.path.exists(config_path):
        create_config_template(config_path)
        sys.exit(0)
        
    config.read(config_path, encoding='utf-8')

    try:
        response_path = config.get('Files', 'response_path')
        content_path = config.get('Files', 'content_path')
        transition_path = config.get('Files', 'transition_path')
        output_wordlist_path = config.get('Files', 'output_wordlist_path')
        output_intdict_path = config.get('Files', 'output_intdict_path')
        combinations = config.getint('Settings', 'combinations')
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        print(f"設定ファイル '{config_path}' の読み込みエラー: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        print("MeCabを初期化しています...")
        tagger = MeCab.Tagger()
    except RuntimeError as e:
        print(f"MeCabの初期化に失敗しました。: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        print("テキストファイルを読み込んでいます...")
        with open(response_path, 'r', encoding='utf-8') as f:
            response_lines = [line.strip() for line in f if line.strip()]
        with open(content_path, 'r', encoding='utf-8') as f:
            content_lines = [line.strip() for line in f if line.strip()]
        with open(transition_path, 'r', encoding='utf-8') as f:
            transition_lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError as e:
        print(f"ファイルが見つかりません: {e.filename}", file=sys.stderr)
        sys.exit(1)

    if not all([response_lines, content_lines, transition_lines]):
        print("エラー: いずれかの入力ファイルが空です。", file=sys.stderr)
        sys.exit(1)
    
    # ▼▼▼ここから処理フローを変更▼▼▼

    # 1. 最初にすべての文章を形態素解析し、単語のリストとして保持する
    print(f"{combinations}通りの会話パターンを生成し、形態素解析します...")
    all_sentences_as_words = []
    for i in range(combinations):
        res = random.choice(response_lines)
        con = random.choice(content_lines)
        tra = random.choice(transition_lines)
        
        combined_text = f"{res} {con} {tra}"
        words = parse_text_to_words(tagger, combined_text)
        all_sentences_as_words.append(words)
        
        if (i + 1) % 500 == 0:
            print(f"  {i + 1}/{combinations} 形態素解析 処理完了...")

    # 2. (後処理) 形態素解析後の全単語リストから、マルコフ連鎖の3単語の組を作成する
    print("\n形態素解析後のデータからマルコフ連鎖の組を作成します... (後処理)")
    all_triplets = []
    for words in all_sentences_as_words:
        triplets = create_triplets_from_words(words)
        all_triplets.extend(triplets)
    
    # ▲▲▲ここまで処理フローを変更▲▲▲

    print("ユニークな単語リストを作成しています...")
    all_words = set(["@BOS@", "@EOS@"])
    for w1, w2, w3 in all_triplets:
        all_words.add(w1)
        all_words.add(w2)
        all_words.add(w3)
    
    id_to_word = sorted(list(all_words))
    word_to_id = {word: i for i, word in enumerate(id_to_word)}

    print("整数ベースの辞書を構築しています...")
    int_markov_data = defaultdict(list)
    start_word_ids = set()

    for w1, w2, w3 in all_triplets:
        if w1 == "@BOS@":
            start_word_ids.add(word_to_id[w2])

        id1 = word_to_id[w1]
        id2 = word_to_id[w2]
        id3 = word_to_id[w3]
        
        long_key = (id1 << 32) | id2
        int_markov_data[long_key].append(id3)

    print(f"'{output_wordlist_path}' を書き込んでいます...")
    try:
        with open(output_wordlist_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(id_to_word))
    except IOError as e:
        print(f"ファイルの書き込みに失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"'{output_intdict_path}' を書き込んでいます...")
    try:
        with open(output_intdict_path, 'w', encoding='utf-8') as f:
            f.write(','.join(map(str, sorted(list(start_word_ids)))) + '\n')
            
            sorted_keys = sorted(int_markov_data.keys())
            for key in sorted_keys:
                value_ids = int_markov_data[key]
                id1 = key >> 32
                id2 = key & 0xFFFFFFFF
                
                value_str = ','.join(map(str, sorted(list(set(value_ids)))))
                f.write(f"{id1},{id2}|{value_str}\n")
    except IOError as e:
        print(f"ファイルの書き込みに失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n完了しました！ 2つの辞書ファイルを生成しました。")
    print(f"- 単語リスト: {output_wordlist_path} ({len(id_to_word)}単語)")
    print(f"- 整数辞書: {output_intdict_path} ({len(int_markov_data)}キー)")

if __name__ == '__main__':
    main()