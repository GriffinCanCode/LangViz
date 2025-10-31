<script lang="ts">
	import { onMount } from 'svelte';
	import { NetworkGraph } from '$viz';
	import { api } from '$api';
	import type { Entry, CognateSet } from '$api';
	
	let container: HTMLDivElement;
	let graph: NetworkGraph;
	let entries: Entry[] = [];
	let cognates: CognateSet[] = [];
	
	onMount(() => {
		graph = new NetworkGraph(container, 1200, 800);
		
		// Load sample data
		loadSampleData();
		
		return () => {
			graph?.destroy();
		};
	});
	
	async function loadSampleData() {
		// TODO: Replace with actual API calls
		// For now, show empty state
	}
</script>

<main class="container">
	<header>
		<h1>LangViz</h1>
		<p>Indo-European Etymology & Semantic Similarity Mapper</p>
	</header>
	
	<section class="controls">
		<button on:click={loadSampleData}>
			Load Sample Data
		</button>
	</section>
	
	<section class="visualization" bind:this={container}>
		<!-- D3 graph will be inserted here -->
	</section>
</main>

<style>
	.container {
		max-width: 1400px;
		margin: 0 auto;
		padding: 2rem;
	}
	
	header {
		text-align: center;
		margin-bottom: 2rem;
	}
	
	h1 {
		font-size: 2.5rem;
		margin: 0;
	}
	
	.controls {
		display: flex;
		gap: 1rem;
		margin-bottom: 2rem;
	}
	
	button {
		padding: 0.5rem 1rem;
		border: 1px solid #ccc;
		border-radius: 4px;
		background: white;
		cursor: pointer;
	}
	
	button:hover {
		background: #f0f0f0;
	}
	
	.visualization {
		border: 1px solid #ddd;
		border-radius: 8px;
		min-height: 600px;
	}
</style>

