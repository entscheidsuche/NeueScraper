<?php
	// Liefert den neuesten Index_*.json eines Spiders. Filter auf den
	// Filename-Prefix 'Index_' (statt aller *.json), damit abweichend
	// benannte Hilfs-Dateien (z.B. aus manuellen Reparaturen oder
	// Failed_Index_*.json) nicht versehentlich als "neuester Lauf"
	// interpretiert werden.
	$spider=$_REQUEST['spider'];
	header('Content-Type: application/json');
	if(strpos($spider, '.') == false){
		$liste=glob('Index/'.$spider.'/Index_*.json');
		if(count($liste)==0){
			$data = ['spider' => $spider, 'job' => 'nojob'];
			print(json_encode($data));
		}
		else {
			rsort($liste);
			$content=file_get_contents ( $liste[0]);
			print($content);
		}
	}
?>
