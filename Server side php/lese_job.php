<?php
	$spider=$_REQUEST['spider'];
	header('Content-Type: application/json');
	if(strpos($spider, '.') == false){
		$liste=glob('Jobs/'.$spider.'/*');
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
