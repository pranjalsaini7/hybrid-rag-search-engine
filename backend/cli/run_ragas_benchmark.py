"""
RAGAS Benchmark Script — Question Generation, A/B Testing, and Local Scoring.
"""

import os
import sys
import json
import random
import argparse
import asyncio
from typing import List, Dict, Any

# Mock langchain_community VertexAI import to prevent Ragas import crash
import types
mod = types.ModuleType('langchain_community.chat_models.vertexai')
mod.ChatVertexAI = object
sys.modules['langchain_community.chat_models.vertexai'] = mod

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.retrieval.vector_store import VectorStore
from app.retrieval.bm25_store import BM25Store
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.reranker import Reranker
from app.chain.qa_chain import QAChain
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Directory to save eval sets
EVAL_SET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "eval_sets")
os.makedirs(EVAL_SET_DIR, exist_ok=True)
GOLDEN_SET_PATH = os.path.join(EVAL_SET_DIR, "golden_test_set.json")
RESULTS_PATH = os.path.join(EVAL_SET_DIR, "ragas_benchmark_results.json")

class RAGASLocalBenchmark:
    def __init__(self):
        self.vector_store = VectorStore()
        # Initialize BM25 store from existing ChromaDB docs
        self.bm25_store = BM25Store()
        docs = self.vector_store.get_all_documents()
        if docs:
            self.bm25_store.build_index(docs)
        
        self.hybrid_retriever = HybridRetriever(self.vector_store, self.bm25_store)
        self.reranker = Reranker()
        
        # Production QA Chain
        self.qa_chain = QAChain(self.hybrid_retriever, self.reranker)
        
        # Initialize judge LLM (llama3)
        self.llm = ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0
        )

    async def generate_golden_test_set(self, testset_size: int = 50) -> List[Dict[str, Any]]:
        """Generate a diverse golden test set of questions using Llama 3."""
        print(f"Loading documents from ChromaDB...")
        docs = self.vector_store.get_all_documents()
        if not docs:
            raise ValueError("No documents found in ChromaDB vector store.")
        print(f"Loaded {len(docs)} document chunks.")

        # Filter docs by filename
        docs_by_source = {}
        for d in docs:
            src = d.metadata.get("source", "unknown")
            if src not in docs_by_source:
                docs_by_source[src] = []
            docs_by_source[src].append(d)

        # Distribute question counts
        n_simple = 15
        n_multihop = 10
        n_comparison = 10
        n_out_of_scope = 5
        n_terminology = 10

        test_set = []

        # Helper to generate via LLM
        async def call_llm(prompt_text: str, inputs: Dict[str, Any]) -> str:
            prompt = ChatPromptTemplate.from_messages([("human", prompt_text)])
            chain = prompt | self.llm | StrOutputParser()
            try:
                res = await chain.ainvoke(inputs)
                return res.strip()
            except Exception as e:
                print(f"LLM generation failed: {e}")
                return ""

        def clean_and_parse_json(text: str) -> Dict[str, Any]:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                json_str = text[start:end+1]
            else:
                json_str = text
            return json.loads(json_str)

        # 1. Simple Factual Questions (~15)
        print("Generating Simple Factual questions...")
        for i in range(n_simple):
            doc = random.choice(docs)
            prompt = """You are a research evaluation dataset generator.
Based ONLY on the following text snippet from '{source}', generate a simple factual question and its ground truth answer.
The question must be directly answerable from the snippet.

Text Snippet:
{text}

Return ONLY a JSON object in this format:
{{"question": "Your question here?", "ground_truth": "The direct factual answer here."}}"""
            res = await call_llm(prompt, {"source": doc.metadata.get("source", "doc"), "text": doc.page_content})
            try:
                data = clean_and_parse_json(res)
                data["question_type"] = "simple_factual"
                test_set.append(data)
                print(f"  [Simple] Q: {data['question']}")
            except Exception as e:
                print(f"  Failed parsing Simple question (Raw: {repr(res)}): {e}")

        # 2. Multi-hop / Reasoning Questions (~10)
        print("Generating Multi-hop / Reasoning questions...")
        for i in range(n_multihop):
            # Select two chunks from the same document
            src = random.choice(list(docs_by_source.keys()))
            src_docs = docs_by_source[src]
            if len(src_docs) < 2:
                # Fallback to random two chunks
                doc_a = random.choice(docs)
                doc_b = random.choice(docs)
            else:
                doc_a, doc_b = random.sample(src_docs, 2)
            
            prompt = """You are a research evaluation dataset generator.
Based on the following two separate text snippets from the same paper, generate one multi-hop reasoning question and its ground truth answer.
The question must require combining information from BOTH snippets to form the correct answer.

Snippet 1:
{text_a}

Snippet 2:
{text_b}

Return ONLY a JSON object in this format:
{{"question": "Your multi-hop question here?", "ground_truth": "The reasoned answer combining both snippets."}}"""
            res = await call_llm(prompt, {"text_a": doc_a.page_content, "text_b": doc_b.page_content})
            try:
                data = clean_and_parse_json(res)
                data["question_type"] = "multi_hop"
                test_set.append(data)
                print(f"  [Multi-hop] Q: {data['question']}")
            except Exception as e:
                print(f"  Failed parsing Multi-hop question (Raw: {repr(res)}): {e}")

        # 3. Comparison Questions (~10)
        print("Generating Comparison questions...")
        for i in range(n_comparison):
            doc_a = random.choice(docs)
            doc_b = random.choice(docs)
            prompt = """You are a research evaluation dataset generator.
Based on the following two text snippets, generate a comparison question and its ground truth answer.
The question should ask to compare or contrast concepts, procedures, or facts mentioned in both snippets.

Snippet A:
{text_a}

Snippet B:
{text_b}

Return ONLY a JSON object in this format:
{{"question": "Your comparison question here?", "ground_truth": "The comparison answer highlighting similarities or differences."}}"""
            res = await call_llm(prompt, {"text_a": doc_a.page_content, "text_b": doc_b.page_content})
            try:
                data = clean_and_parse_json(res)
                data["question_type"] = "comparison"
                test_set.append(data)
                print(f"  [Comparison] Q: {data['question']}")
            except Exception as e:
                print(f"  Failed parsing Comparison question (Raw: {repr(res)}): {e}")

        # 4. Out-of-scope / Negative Questions (~5)
        print("Generating Out-of-scope questions...")
        out_of_scope_topics = [
            "How does quantum computing affect modern RAG search engines?",
            "What are the specific recipes for baking an authentic sourdough bread at high altitudes?",
            "Can you explain the historical causes of the Peloponnesian War in ancient Greece?",
            "What is the current stock price and financial forecast of Nvidia for the next quarter?",
            "Explain the steps to replace a transmission fluid in a 2018 Honda Civic.",
            "Describe the molecular structure and chemical properties of caffeine."
        ]
        for topic in random.sample(out_of_scope_topics, min(n_out_of_scope, len(out_of_scope_topics))):
            test_set.append({
                "question": topic,
                "ground_truth": "I am sorry, but the provided documents do not contain information to answer this question.",
                "question_type": "out_of_scope"
            })
            print(f"  [Out-of-scope] Q: {topic}")

        # 5. Terminology / Acronym-heavy Questions (~10)
        print("Generating Terminology / Acronym questions...")
        for i in range(n_terminology):
            doc = random.choice(docs)
            prompt = """You are a research evaluation dataset generator.
Based on the following text snippet, find any complex acronyms, technical terms, or domain-specific terminology.
Generate a question specifically testing the meaning, definition, or context of that terminology or acronym, along with its ground truth answer.

Snippet:
{text}

Return ONLY a JSON object in this format:
{{"question": "Your terminology-specific question here?", "ground_truth": "The correct definition or usage explanation."}}"""
            res = await call_llm(prompt, {"text": doc.page_content})
            try:
                data = clean_and_parse_json(res)
                data["question_type"] = "terminology"
                test_set.append(data)
                print(f"  [Terminology] Q: {data['question']}")
            except Exception as e:
                print(f"  Failed parsing Terminology question (Raw: {repr(res)}): {e}")

        # Ensure we have clean, unique questions
        seen = set()
        unique_test_set = []
        for item in test_set:
            q = item.get("question", "").strip()
            if q and q not in seen:
                seen.add(q)
                unique_test_set.append(item)

        with open(GOLDEN_SET_PATH, "w", encoding="utf-8") as f:
            json.dump(unique_test_set, f, indent=2, ensure_ascii=False)

        print(f"Saved {len(unique_test_set)} unique golden questions to {GOLDEN_SET_PATH}")
        return unique_test_set

    async def evaluate_pipeline(self, test_set: List[Dict[str, Any]], use_reranker: bool) -> List[Dict[str, Any]]:
        """Run the test set through the production pipeline and return results."""
        results = []
        
        # Override config setting temporarily
        settings.DISABLE_RERANKER = not use_reranker
        print(f"\nRunning evaluation pipeline (Reranker={use_reranker})...")
        
        for idx, item in enumerate(test_set):
            question = item["question"]
            gt = item["ground_truth"]
            q_type = item["question_type"]
            
            print(f"  [{idx+1}/{len(test_set)}] Q: {question[:60]}...")
            
            # 1. Retrieve context
            search_query = await self.qa_chain._condense_question(question, "")
            candidates = self.hybrid_retriever.retrieve(search_query)
            
            # Apply rerank if enabled
            if use_reranker:
                retrieved_docs = self.reranker.rerank(search_query, candidates)
            else:
                retrieved_docs = candidates[:settings.TOP_K_FINAL]
                
            # 2. Generate answer
            context_str = self.qa_chain._format_context(retrieved_docs)
            prompt = ChatPromptTemplate.from_messages([
                ("system", self.qa_chain.SYSTEM_PROMPT if hasattr(self.qa_chain, "SYSTEM_PROMPT") else "Answer the question based only on context."),
                ("human", "{question}"),
            ])
            
            try:
                # Use qa_chain LLM
                chain = prompt | self.qa_chain.llm | StrOutputParser()
                answer = await chain.ainvoke({
                    "context": context_str,
                    "question": question,
                    "history": "(No prior conversation)"
                })
            except Exception as e:
                print(f"    Failed generation: {e}")
                answer = "Error generating answer."

            results.append({
                "question": question,
                "question_type": q_type,
                "ground_truth": gt,
                "answer": answer,
                "retrieved_contexts": [d.page_content for d in retrieved_docs]
            })
            
        return results

    async def compute_ragas_scores(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute Faithfulness, Answer Relevancy, Context Precision, and Context Recall using local LLM judge."""
        scores_list = []
        total_f = total_ar = total_cp = total_cr = 0.0
        
        print("\nScoring RAGAS metrics locally...")
        for idx, res in enumerate(results):
            q = res["question"]
            ans = res["answer"]
            gt = res["ground_truth"]
            contexts = res["retrieved_contexts"]
            q_type = res["question_type"]
            
            # 1. Faithfulness
            faithfulness = 1.0
            if contexts and ans and q_type != "out_of_scope":
                prompt = """You are an evaluation judge.
Check if the generated Answer is factually supported by the provided Context.
Answer: {answer}
Context: {context}

Rate the Faithfulness from 0.0 (completely hallucinated/unsupported) to 1.0 (fully supported).
Return ONLY the numerical float value (e.g. 0.85)."""
                val_str = await self._score_llm(prompt, {"answer": ans, "context": "\n".join(contexts)})
                try:
                    faithfulness = float(val_str)
                except:
                    faithfulness = 0.5
            elif q_type == "out_of_scope":
                # For out of scope, if the system says it doesn't know, it's highly faithful
                if "provided documents do not contain" in ans.lower() or "sorry" in ans.lower() or "do not have information" in ans.lower():
                    faithfulness = 1.0
                else:
                    faithfulness = 0.0

            # 2. Answer Relevancy
            answer_relevancy = 1.0
            if ans and q:
                prompt = """You are an evaluation judge.
Rate how directly and completely the Answer addresses the Question asked.
Question: {question}
Answer: {answer}

Rate the Answer Relevancy from 0.0 (completely irrelevant) to 1.0 (perfectly relevant and directly addresses the question).
Return ONLY the numerical float value (e.g. 0.90)."""
                val_str = await self._score_llm(prompt, {"question": q, "answer": ans})
                try:
                    answer_relevancy = float(val_str)
                except:
                    answer_relevancy = 0.5

            # 3. Context Precision
            context_precision = 1.0
            if contexts and q_type != "out_of_scope":
                prompt = """You are an evaluation judge.
Rate the quality of the retrieved context chunks. Are the top chunks highly relevant to answering the question?
Question: {question}
Top Chunks: {context}

Rate the Context Precision from 0.0 (no relevant chunks at the top) to 1.0 (all top chunks are highly relevant).
Return ONLY the numerical float value (e.g. 0.95)."""
                val_str = await self._score_llm(prompt, {"question": q, "context": "\n\n".join(contexts[:2])})
                try:
                    context_precision = float(val_str)
                except:
                    context_precision = 0.5

            # 4. Context Recall
            context_recall = 1.0
            if contexts and gt and q_type != "out_of_scope":
                prompt = """You are an evaluation judge.
Rate if the retrieved contexts contain all the necessary details present in the Ground Truth answer to answer the question.
Ground Truth: {gt}
Retrieved Contexts: {context}

Rate the Context Recall from 0.0 (none of the ground truth facts are in the context) to 1.0 (all ground truth facts are present).
Return ONLY the numerical float value (e.g. 0.80)."""
                val_str = await self._score_llm(prompt, {"gt": gt, "context": "\n\n".join(contexts)})
                try:
                    context_recall = float(val_str)
                except:
                    context_recall = 0.5
            elif q_type == "out_of_scope":
                context_recall = 1.0

            scores_list.append({
                "faithfulness": faithfulness,
                "answer_relevancy": answer_relevancy,
                "context_precision": context_precision,
                "context_recall": context_recall
            })
            
            total_f += faithfulness
            total_ar += answer_relevancy
            total_cp += context_precision
            total_cr += context_recall
            print(f"    Scored Q{idx+1}: F={faithfulness:.2f}, AR={answer_relevancy:.2f}, CP={context_precision:.2f}, CR={context_recall:.2f}")

        n = len(results)
        return {
            "aggregate": {
                "faithfulness": total_f / n,
                "answer_relevancy": total_ar / n,
                "context_precision": total_cp / n,
                "context_recall": total_cr / n
            },
            "per_question": scores_list
        }

    async def _score_llm(self, prompt_text: str, inputs: Dict[str, Any]) -> str:
        prompt = ChatPromptTemplate.from_messages([("human", prompt_text)])
        chain = prompt | self.llm | StrOutputParser()
        try:
            res = await chain.ainvoke(inputs)
            # clean non-numeric text
            cleaned = "".join([c for c in res.strip() if c.isdigit() or c == "."])
            return cleaned if cleaned else "0.5"
        except:
            return "0.5"

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-only", action="store_true", help="Generate golden test set and exit.")
    parser.add_argument("--run-eval", action="store_true", help="Run the pipeline evaluation and scoring.")
    args = parser.parse_args()

    benchmark = RAGASLocalBenchmark()

    if args.generate_only:
        await benchmark.generate_golden_test_set()
        return

    # Check if test set exists, if not generate it
    if not os.path.exists(GOLDEN_SET_PATH):
        print("Golden test set not found. Generating it now...")
        test_set = await benchmark.generate_golden_test_set()
    else:
        with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
            test_set = json.load(f)
        print(f"Loaded {len(test_set)} golden questions from {GOLDEN_SET_PATH}")

    if args.run_eval:
        # Run A/B test
        # 1. Run without Reranker
        results_without = await benchmark.evaluate_pipeline(test_set, use_reranker=False)
        scores_without = await benchmark.compute_ragas_scores(results_without)

        # 2. Run with Reranker
        results_with = await benchmark.evaluate_pipeline(test_set, use_reranker=True)
        scores_with = await benchmark.compute_ragas_scores(results_with)

        # Compile report
        report = {
            "without_reranker": {
                "results": results_without,
                "scores": scores_without
            },
            "with_reranker": {
                "results": results_with,
                "scores": scores_with
            }
        }

        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nSaved evaluation results to {RESULTS_PATH}")

        # Compute metric changes
        agg_w = scores_without["aggregate"]
        agg_r = scores_with["aggregate"]

        def calc_imp(w, r):
            if w == 0:
                return 0.0
            return ((r - w) / w) * 100

        print("\n" + "="*50)
        print(" RAGAS BENCHMARK SUMMARY REPORT")
        print("="*50)
        print(f"{'Metric':<20} | {'Without Reranker':<16} | {'With Reranker':<16} | {'Improvement':<12}")
        print("-"*70)
        for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            w = agg_w[metric]
            r = agg_r[metric]
            imp = calc_imp(w, r)
            print(f"{metric:<20} | {w*100:>14.1f}% | {r*100:>14.1f}% | {imp:>+10.1f}%")
        print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
