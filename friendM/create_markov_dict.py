import MeCab
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
        if word and node.posid != 0:
            words.append(word)
        node = node.next
    return words

def create_triplets_from_words(words):
    """単語リストからマルコフ連鎖用の3単語の組を作成する"""
    if len(words) < 2:
        return []
    tokens = ["@BOS@"] + words + ["@EOS@"]
    triplets = []
    for i in range(len(tokens) - 2):
        w1, w2, w3 = tokens[i], tokens[i + 1], tokens[i + 2]
        triplets.append((w1, w2, w3))
    return triplets

def create_config_template(config_path):
    """設定ファイルのテンプレートを生成する"""
    config = configparser.ConfigParser()
    config["Files"] = {
        "content_path": "content.json",
        "output_wordlist_path": "ContentWordList.txt",
        "output_intdict_path": "ContentIntDict.txt"
    }
    with open(config_path, "w", encoding="utf-8") as f:
        config.write(f)
    print(f"設定ファイル '{config_path}' が見つからなかったためテンプレートを生成しました。")
    print("ファイルパスを編集してから再実行してください。")

def main():
    config_path = "config.ini"
    config = configparser.ConfigParser()
    if not os.path.exists(config_path):
        create_config_template(config_path)
        sys.exit(0)
    config.read(config_path, encoding="utf-8")

    try:
        content_path = config.get("Files", "content_path")
        output_wordlist_path = config.get("Files", "output_wordlist_path")
        output_intdict_path = config.get("Files", "output_intdict_path")
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
        with open(content_path, "r", encoding="utf-8") as f:
            content_lines = json.load(f)
        if not isinstance(content_lines, list) or not all(isinstance(item, str) for item in content_lines):
            raise TypeError("JSONファイルは文字列の配列である必要があります。")
    except (FileNotFoundError, json.JSONDecodeError, TypeError) as e:
        print(f"ファイルの読み込み中にエラー: {e}", file=sys.stderr)
        sys.exit(1)

    print("形態素解析とマルコフデータの構築を開始します...")
    all_triplets = []
    for line in content_lines:
        words = parse_text_to_words(tagger, line)
        triplets = create_triplets_from_words(words)
        all_triplets.extend(triplets)

    print("ユニークな単語リストを作成中...")
    all_words = set(["@BOS@", "@EOS@"])
    for w1, w2, w3 in all_triplets:
        all_words.update([w1, w2, w3])

    id_to_word = sorted(list(all_words))
    word_to_id = {word: i for i, word in enumerate(id_to_word)}

    print("整数ベースの辞書を生成中...")
    int_markov_data = defaultdict(list)
    start_word_ids = set()

    for w1, w2, w3 in all_triplets:
        if w1 == "@BOS@":
            start_word_ids.add(word_to_id[w2])
        id1, id2, id3 = word_to_id[w1], word_to_id[w2], word_to_id[w3]

        # C# と完全一致するキー生成方式
        long_key = (int(id1) << 32) | (int(id2) & 0xFFFFFFFF)
        int_markov_data[long_key].append(id3)

    print("フラット配列を構築中...")
    sorted_keys = sorted(int_markov_data.keys())
    all_candidates = []
    key_info = []

    for key in sorted_keys:
        unique_candidates = sorted(set(int_markov_data[key]))
        start_index = len(all_candidates)
        length = len(unique_candidates)
        all_candidates.extend(unique_candidates)
        key_info.append((key, start_index, length))

    print(f"'{output_wordlist_path}' に単語リストを書き込み中...")
    with open(output_wordlist_path, "w", encoding="utf-8") as f:
        f.write("\n".join(id_to_word))

    print(f"'{output_intdict_path}' に辞書データを書き込み中...")
    with open(output_intdict_path, "w", encoding="utf-8") as f:
        # 1行目: 開始単語IDリスト
        f.write(",".join(map(str, sorted(start_word_ids))) + "\n")

        # 2行目以降: キー情報 (id1,id2|start,length)
        for key, start_idx, length in key_info:
            id1 = key >> 32
            id2 = key & 0xFFFFFFFF
            f.write(f"{id1},{id2}|{start_idx},{length}\n")

        # 最終行: 全候補配列
        f.write(",".join(map(str, all_candidates)) + "\n")

    print("\n✅ 完了しました！")
    print(f"登録単語数: {len(id_to_word)}")
    print(f"マルコフキー数: {len(sorted_keys)}")
    print(f"全候補数: {len(all_candidates)}")
    print(f"推定メモリ節約: 約{len(sorted_keys)*8/(1024*1024):.2f}MB")

if __name__ == "__main__":
    main()
