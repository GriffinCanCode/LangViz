/**
 * Network graph visualization using D3.js.
 * 
 * Renders cognate networks with force-directed layout.
 */

import * as d3 from 'd3';
import type { CognateSet, Entry } from '$api';

export interface NetworkNode extends d3.SimulationNodeDatum {
	id: string;
	label: string;
	group: string;
	entry: Entry;
}

export interface NetworkLink extends d3.SimulationLinkDatum<NetworkNode> {
	source: string | NetworkNode;
	target: string | NetworkNode;
	weight: number;
}

export class NetworkGraph {
	private svg: d3.Selection<SVGSVGElement, unknown, null, undefined>;
	private simulation: d3.Simulation<NetworkNode, NetworkLink>;
	private nodes: NetworkNode[] = [];
	private links: NetworkLink[] = [];
	
	constructor(
		container: HTMLElement,
		width: number = 800,
		height: number = 600
	) {
		this.svg = d3.select(container)
			.append('svg')
			.attr('width', width)
			.attr('height', height);
		
		this.simulation = d3.forceSimulation<NetworkNode, NetworkLink>()
			.force('link', d3.forceLink<NetworkNode, NetworkLink>().id(d => d.id))
			.force('charge', d3.forceManyBody().strength(-300))
			.force('center', d3.forceCenter(width / 2, height / 2));
	}
	
	setData(entries: Entry[], cognateSets: CognateSet[]) {
		// Build nodes from entries
		this.nodes = entries.map(entry => ({
			id: entry.id,
			label: entry.headword,
			group: entry.language,
			entry,
		}));
		
		// Build links from cognate sets
		this.links = [];
		for (const set of cognateSets) {
			for (let i = 0; i < set.entries.length; i++) {
				for (let j = i + 1; j < set.entries.length; j++) {
					this.links.push({
						source: set.entries[i],
						target: set.entries[j],
						weight: set.confidence,
					});
				}
			}
		}
		
		this.render();
	}
	
	private render() {
		// Draw links
		const link = this.svg.append('g')
			.selectAll('line')
			.data(this.links)
			.join('line')
			.attr('stroke', '#999')
			.attr('stroke-opacity', d => d.weight)
			.attr('stroke-width', d => Math.sqrt(d.weight * 5));
		
		// Draw nodes
		const node = this.svg.append('g')
			.selectAll('circle')
			.data(this.nodes)
			.join('circle')
			.attr('r', 8)
			.attr('fill', d => this.colorByLanguage(d.group))
			.call(this.drag());
		
		// Add labels
		const label = this.svg.append('g')
			.selectAll('text')
			.data(this.nodes)
			.join('text')
			.text(d => d.label)
			.attr('font-size', 10)
			.attr('dx', 12)
			.attr('dy', 4);
		
		// Update positions on simulation tick
		this.simulation
			.nodes(this.nodes)
			.on('tick', () => {
				link
					.attr('x1', d => (d.source as NetworkNode).x!)
					.attr('y1', d => (d.source as NetworkNode).y!)
					.attr('x2', d => (d.target as NetworkNode).x!)
					.attr('y2', d => (d.target as NetworkNode).y!);
				
				node
					.attr('cx', d => d.x!)
					.attr('cy', d => d.y!);
				
				label
					.attr('x', d => d.x!)
					.attr('y', d => d.y!);
			});
		
		this.simulation.force<d3.ForceLink<NetworkNode, NetworkLink>>('link')!
			.links(this.links);
	}
	
	private colorByLanguage(language: string): string {
		const colors = d3.schemeCategory10;
		const hash = Array.from(language).reduce((acc, char) => acc + char.charCodeAt(0), 0);
		return colors[hash % colors.length];
	}
	
	private drag() {
		function dragstarted(event: d3.D3DragEvent<SVGCircleElement, NetworkNode, NetworkNode>) {
			if (!event.active) (this as NetworkGraph).simulation.alphaTarget(0.3).restart();
			event.subject.fx = event.subject.x;
			event.subject.fy = event.subject.y;
		}
		
		function dragged(event: d3.D3DragEvent<SVGCircleElement, NetworkNode, NetworkNode>) {
			event.subject.fx = event.x;
			event.subject.fy = event.y;
		}
		
		function dragended(event: d3.D3DragEvent<SVGCircleElement, NetworkNode, NetworkNode>) {
			if (!event.active) (this as NetworkGraph).simulation.alphaTarget(0);
			event.subject.fx = null;
			event.subject.fy = null;
		}
		
		return d3.drag<SVGCircleElement, NetworkNode>()
			.on('start', dragstarted.bind(this))
			.on('drag', dragged)
			.on('end', dragended.bind(this));
	}
	
	destroy() {
		this.simulation.stop();
		this.svg.remove();
	}
}

