import MeCab
import random
import configparser
import sys
import os
import json
from collections import defaultdict

def parse_text_to_words(tagger, text):
    """MeCabを使って文章を単語のリストに分割する"""
    node = tagger.parseToNode(text)
    words = []
    while node:
        word = node.surface
        # 空文字やBOS/EOSは除外
        if word and word != 'BOS' and word != 'EOS' and node.posid != 0:
            words.append(word)
        node = node.next
    return words

def create_triplets_from_words(words):
    """単語リストからマルコフ連鎖用の3単語の組を作成する"""
    if len(words) < 1:
        return []
    # BOSとEOSを明示的に追加
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
        'content_path': 'content.json',
        'output_wordlist_path': 'ContentWordList.txt',
        'output_intdict_path': 'ContentIntDict.txt'
    }
    with open(config_path, 'w', encoding='utf-8') as f:
        config.write(f)
    print(f"設定ファイル '{config_path}' が見つからなかったため、テンプレートを生成しました。")
    print("ファイルパスを編集してから、再度スクリプトを実行してください。")

def main():
    config_path = 'config.ini'
    config = configparser.ConfigParser()
    if not os.path.exists(config_path):
        create_config_template(config_path)
        sys.exit(0)
    config.read(config_path, encoding='utf-8')

    try:
        content_path = config.get('Files', 'content_path')
        output_wordlist_path = config.get('Files', 'output_wordlist_path')
        output_intdict_path = config.get('Files', 'output_intdict_path')
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        print(f"設定ファイル '{config_path}' の読み込みエラー: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        tagger = MeCab.Tagger()
    except RuntimeError as e:
        print(f"MeCabの初期化に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        print(f"'{content_path}' を読み込んでいます...")
        with open(content_path, 'r', encoding='utf-8') as f:
            content_lines = json.load(f)
        if not isinstance(content_lines, list) or not all(isinstance(item, str) for item in content_lines):
            raise TypeError("JSONファイルは文字列の配列である必要があります。")
    except (FileNotFoundError, json.JSONDecodeError, TypeError) as e:
        print(f"ファイルの読み込み中にエラーが発生しました: {e}", file=sys.stderr)
        sys.exit(1)

    print("形態素解析とデータ作成を開始します...")
    all_triplets = []
    for line in content_lines:
        words = parse_text_to_words(tagger, line)
        triplets = create_triplets_from_words(words)
        all_triplets.extend(triplets)

    print("BOS/EOSを固定IDにマッピング...")
    # BOSを0、EOSを1に固定
    word_to_id = {
        "@BOS@": 0,
        "@EOS@": 1
    }
    id_to_word = ["@BOS@", "@EOS@"]
    
    # 通常の単語を追加
    unique_words = set()
    for w1, w2, w3 in all_triplets:
        unique_words.add(w1)
        unique_words.add(w2)
        unique_words.add(w3)
    
    # BOS/EOSを除く
    unique_words.discard("@BOS@")
    unique_words.discard("@EOS@")
    
    # 通常の単語にIDを割り当て
    for word in sorted(unique_words):
        word_to_id[word] = len(word_to_id)
        id_to_word.append(word)
    
    print(f"単語数: {len(id_to_word)} (BOS/EOS含む)")

    print("整数ベースの辞書を構築しています...")
    markov_chain = defaultdict(list)
    # (BOS,BOS)からの遷移を特別に記録
    start_word_ids = []
    
    for w1, w2, w3 in all_triplets:
        id1, id2, id3 = word_to_id[w1], word_to_id[w2], word_to_id[w3]
        
        # (BOS,BOS)からの遷移を記録
        if w1 == "@BOS@" and w2 == "@BOS@":
            start_word_ids.append(id3)
        
        # マルコフ連鎖データに追加
        markov_chain[(id1, id2)].append(id3)

    # 重複を除去し、フラット配列を構築
    print("フラット配列を構築しています...")
    # キーをソートして一貫性を確保
    sorted_keys = sorted(markov_chain.keys())
    
    all_candidates = []  # 全候補を一列に
    key_info = []  # (key, start_index, length)
    
    for key in sorted_keys:
        # 重複除去とソート
        unique_candidates = sorted(list(set(markov_chain[key])))
        start_index = len(all_candidates)
        length = len(unique_candidates)
        all_candidates.extend(unique_candidates)
        key_info.append((key, start_index, length))

    print(f"'{output_wordlist_path}' を書き込んでいます...")
    with open(output_wordlist_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(id_to_word))

    print(f"'{output_intdict_path}' を書き込んでいます...")
    with open(output_intdict_path, 'w', encoding='utf-8') as f:
        # 1行目: 開始単語IDリスト（(BOS,BOS)からの遷移）
        f.write(','.join(map(str, start_word_ids)) + '\n')
        
        # 2行目以降: キー情報
        for (id1, id2), start_idx, length in key_info:
            f.write(f"{id1},{id2}|{start_idx},{length}\n")
        
        # 最終行: 全候補配列
        f.write(','.join(map(str, all_candidates)))

    print("\n完了しました！")
    print(f"単語数: {len(id_to_word)}")
    print(f"遷移数: {len(key_info)}")
    print(f"候補単語数: {len(all_candidates)}")
    print(f"推定メモリ使用量: 約{len(key_info) * 8 / (1024*1024):.2f}MB")

if __name__ == '__main__':
    main()