<script>
  import CounterCard from "./CounterCard.svelte";
  let total = $state(0);
  const incrementTotal = () => total = Math.min(369, total + 1);
</script>
<main>
  <h1>Two counters. One language.</h1>
  <p data-bench-shared>Shared total across cards: {total}</p>
  <button type="button" onclick={() => total = 0}>Reset shared total</button>
  <CounterCard label="Alpha" {total} {incrementTotal} />
  <CounterCard label="Beta" {total} {incrementTotal} />
</main>
