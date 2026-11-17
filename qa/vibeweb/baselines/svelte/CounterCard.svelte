<script>
  let { label, total, incrementTotal } = $props();
  let count = $state(0);
</script>
<section aria-label={label}>
  <h2>{label}</h2>
  <p>{label}: {count} clicks. Shared total: {total}</p>
  <button type="button" onclick={() => count = Math.min(9, count + 1)}>Increment local</button>
  <button type="button" onclick={incrementTotal}>Increment total</button>
</section>
